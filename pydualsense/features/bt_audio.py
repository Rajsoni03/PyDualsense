"""
Bluetooth audio streaming for DualSense via HID report 0x36.

The DualSense accepts 398-byte audio output reports over BT HID (interrupt
channel) that carry:
  - 63 bytes of controller state (LEDs, triggers)
  - 64 bytes of 3 kHz haptic PCM (int8 stereo)
  - 200 bytes of Opus-encoded speaker audio (48 kHz stereo, CBR 160 kbps,
    10 ms frames = 480 samples/channel)
  - CRC-32 over first 394 bytes with seed byte 0xA2 (same as report 0x31)

Report 0x36 layout (398 bytes total):
  [0]       0x36  — report ID
  [1]       seq << 4  — 4-bit rolling counter in upper nibble
  [2]       0x91  — header flags (0x11 | 0x80)
  [3]       0x07
  [4]       0xFE
  [5..9]    audio_buf_len  — controller audio buffer depth (all same value)
  [10]      pkt_counter  — incremental uint8
  [11]      0x90  — state section header (0x10 | 0x80)
  [12]      63    — state section length
  [13..75]  state_bytes  — 63 bytes of controller state
  [76]      0x92  — haptics section header (0x12 | 0x80)
  [77]      64    — haptics section length
  [78..141] haptic_buf  — 64 bytes of int8 stereo 3 kHz haptics (zeros = off)
  [142]     0x93  — speaker section header (0x13 | 0x80)
  [143]     200   — speaker section length
  [144..343] opus_buf  — 200-byte CBR Opus packet
  [344..393] zeros  — padding
  [394..397] CRC-32 little-endian

State bytes (63) match DS5Dongle state_init_data (awalol/DS5Dongle):
  flag0=0xfd, flag1=0xf7, audio_ctrl=0x09, power_save=0x0F,
  audio_ctrl_2=0x0a, valid_flag2=0x07

CRC uses same algorithm as report 0x31: crc32(0xA2 ‖ pkt[:394]).

Opus encoding uses cffi + libopus because ctypes cannot correctly call
variadic C functions on ARM64 macOS.

Install dependencies:
    pip install cffi sounddevice numpy
    brew install opus   (macOS; the cffi path uses the Homebrew dylib directly)
"""

import binascii
import math
import time
import threading
import ctypes.util
import os
import struct
from typing import Callable, Optional

_OPUS_FRAME_SAMPLES = 480       # 10 ms at 48 kHz
_OPUS_SAMPLE_RATE   = 48000
_OPUS_CHANNELS      = 2
_OPUS_MAX_BYTES     = 200       # max / target CBR packet size
_OPUS_BITRATE       = 160000    # 200 bytes × 8 × 100 fps = 160 kbps
_OPUS_APPLICATION_AUDIO = 2049

_BT_AUDIO_REPORT_ID   = 0x36
_BT_AUDIO_REPORT_SIZE = 398
_AUDIO_BUF_LEN        = 48     # controller audio buffer depth

# ── libopus via cffi ──────────────────────────────────────────────────────────

def _find_libopus() -> str:
    """Return the path to libopus, preferring Homebrew on macOS."""
    candidates = [
        "/opt/homebrew/lib/libopus.dylib",   # macOS ARM64 (Apple Silicon)
        "/usr/local/lib/libopus.dylib",      # macOS x86_64
        "/usr/lib/libopus.so.0",             # Linux
        "/usr/lib/x86_64-linux-gnu/libopus.so.0",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    name = ctypes.util.find_library("opus")
    if name:
        return name
    raise OSError(
        "libopus not found.  "
        "macOS: brew install opus   Linux: apt install libopus-dev"
    )


def _make_opus_ffi():
    try:
        import cffi
    except ImportError:
        return None, None
    ffi = cffi.FFI()
    ffi.cdef("""
        typedef struct OpusEncoder OpusEncoder;
        OpusEncoder *opus_encoder_create(int Fs, int channels, int application,
                                         int *error);
        void         opus_encoder_destroy(OpusEncoder *st);
        int          opus_encoder_ctl(OpusEncoder *st, int request, ...);
        int          opus_encode(OpusEncoder *st, const short *pcm,
                                 int frame_size, unsigned char *data,
                                 int max_data_bytes);
    """)
    try:
        lib = ffi.dlopen(_find_libopus())
        return ffi, lib
    except Exception:
        return None, None


_ffi, _opus_lib = _make_opus_ffi()

_HAS_OPUS = _ffi is not None and _opus_lib is not None


class _OpusEncoder:
    """Thin CBR Opus encoder (48 kHz stereo, 200-byte 10 ms frames)."""

    def __init__(self) -> None:
        if not _HAS_OPUS:
            raise RuntimeError(
                "cffi/libopus not available — "
                "pip install cffi && brew install opus"
            )
        err_p = _ffi.new("int *")
        self._enc = _opus_lib.opus_encoder_create(
            _OPUS_SAMPLE_RATE, _OPUS_CHANNELS, _OPUS_APPLICATION_AUDIO, err_p
        )
        if err_p[0] != 0:
            raise RuntimeError(f"opus_encoder_create error {err_p[0]}")

        # cffi requires explicit cdata for variadic args on ARM64
        r = _opus_lib.opus_encoder_ctl(
            self._enc,
            4002,                           # OPUS_SET_BITRATE_REQUEST
            _ffi.cast("int", _OPUS_BITRATE)
        )
        if r != 0:
            raise RuntimeError(f"OPUS_SET_BITRATE failed: {r}")

        r = _opus_lib.opus_encoder_ctl(
            self._enc,
            4006,                           # OPUS_SET_VBR_REQUEST = CBR
            _ffi.cast("int", 0)
        )
        if r != 0:
            raise RuntimeError(f"OPUS_SET_VBR failed: {r}")

        self._out = _ffi.new(f"unsigned char[{_OPUS_MAX_BYTES}]")

    def encode(self, pcm_int16: bytes) -> bytes:
        """Encode one 480-frame (10 ms) stereo int16 PCM chunk → 200-byte packet."""
        pcm_p = _ffi.cast("short *", _ffi.from_buffer(pcm_int16))
        n = _opus_lib.opus_encode(
            self._enc, pcm_p, _OPUS_FRAME_SAMPLES, self._out, _OPUS_MAX_BYTES
        )
        if n < 0:
            raise RuntimeError(f"opus_encode error {n}")
        raw = bytes(_ffi.buffer(self._out, n))
        # Pad to exactly 200 bytes; Opus decoders ignore trailing zeros.
        return raw + b"\x00" * (_OPUS_MAX_BYTES - len(raw))

    def __del__(self) -> None:
        if _HAS_OPUS and hasattr(self, "_enc"):
            try:
                _opus_lib.opus_encoder_destroy(self._enc)
            except Exception:
                pass


# ── State bytes helper ────────────────────────────────────────────────────────

# Base state mirroring DS5Dongle state_init_data (awalol/DS5Dongle src/state_mgr.cpp).
# 63 bytes = output report buf[3:66].  Indices below are state-slice indices
# (state[i] = buf[3+i]).
#
#  state[0]  = flag0            0xfd  (all enable bits)
#  state[1]  = flag1            0xf7  (all, custom lightbar)
#  state[4]  = headphone_vol    0x7f
#  state[5]  = speaker_vol      0x64  (overridden per call)
#  state[6]  = mic_vol          0xff
#  state[7]  = audio_ctrl       0x09  ← BT-specific; USB uses 0x30
#  state[9]  = power_save_mute  0x0F
#  state[37] = audio_ctrl_2     0x0a
#  state[38] = valid_flag2      0x07
#  state[41] = lightbar_setup   0x02  (LIGHTBAR_RELEASE)
#  state[42] = led_brightness   0x01  (mid)
#  state[44] = lightbar_red     0xff  (overridden per call)
#  state[45] = lightbar_green   0xd7  (overridden per call)
#  state[46] = lightbar_blue    0x00  (overridden per call)
_BT_STATE_BASE = bytearray(63)
_BT_STATE_BASE[0]  = 0xfd   # flag0
_BT_STATE_BASE[1]  = 0xf7   # flag1
_BT_STATE_BASE[4]  = 0x7f   # headphone_vol
_BT_STATE_BASE[5]  = 0x64   # speaker_vol default (100)
_BT_STATE_BASE[6]  = 0xff   # mic_vol
_BT_STATE_BASE[7]  = 0x09   # audio_ctrl (BT-specific value)
_BT_STATE_BASE[9]  = 0x0F   # power_save_mute_ctrl
_BT_STATE_BASE[37] = 0x0a   # audio_ctrl_2
_BT_STATE_BASE[38] = 0x07   # valid_flag2
_BT_STATE_BASE[41] = 0x02   # lightbar_setup (LIGHTBAR_RELEASE)
_BT_STATE_BASE[42] = 0x01   # led_brightness (mid)
_BT_STATE_BASE[44] = 0xff   # lightbar_red
_BT_STATE_BASE[45] = 0xd7   # lightbar_green
_BT_STATE_BASE[46] = 0x00   # lightbar_blue


def make_bt_state_bytes(
    speaker_vol: int = 100,
    r: int = 0,
    g: int = 0,
    b: int = 200,
) -> bytes:
    """Return a 63-byte state slice compatible with BT audio report 0x36.

    Based on the DS5Dongle-verified state_init_data; overrides speaker volume
    and lightbar colour.

    state[i] maps to output report buf[3+i]:
      speaker_vol → state[5]  = buf[8]
      lightbar    → state[44-46] = buf[47-49]

    Args:
        speaker_vol: Built-in speaker volume 0–255.
        r, g, b:     Lightbar colour 0–255 each.
    """
    state = bytearray(_BT_STATE_BASE)
    state[5]  = max(0, min(255, speaker_vol))
    state[44] = max(0, min(255, r))
    state[45] = max(0, min(255, g))
    state[46] = max(0, min(255, b))
    return bytes(state)


# ── Report 0x36 builder ───────────────────────────────────────────────────────

def _append_bt_audio_crc(pkt: bytearray) -> None:
    """Append CRC-32 to a BT audio report 0x36 in place (last 4 bytes).

    Same algorithm as standard output report 0x31: CRC over the concatenation
    of seed byte 0xA2 and the first 394 bytes of the 398-byte packet.
    """
    crc = binascii.crc32(bytes([0xA2]) + bytes(pkt[:394])) & 0xFFFFFFFF
    pkt[394:398] = struct.pack("<I", crc)


def build_bt_audio_report(
    opus_bytes: bytes,
    state_bytes: bytes,
    seq: int,
    pkt_ctr: int,
) -> bytes:
    """Build a 398-byte DualSense BT audio output report (ID 0x36) with CRC.

    Args:
        opus_bytes:  200-byte CBR Opus packet for the built-in speaker.
        state_bytes: 63-byte controller state from :func:`make_bt_state_bytes`.
        seq:         4-bit rolling counter (0–15).
        pkt_ctr:     Incremental uint8 packet counter.

    Returns:
        398-byte bytes object ready to pass to ``hid.Device.write()``.
    """
    pkt = bytearray(_BT_AUDIO_REPORT_SIZE)

    pkt[0]  = _BT_AUDIO_REPORT_ID         # 0x36
    pkt[1]  = (seq & 0x0F) << 4
    pkt[2]  = 0x11 | 0x80                 # 0x91
    pkt[3]  = 0x07
    pkt[4]  = 0xFE
    pkt[5]  = _AUDIO_BUF_LEN
    pkt[6]  = _AUDIO_BUF_LEN
    pkt[7]  = _AUDIO_BUF_LEN
    pkt[8]  = _AUDIO_BUF_LEN
    pkt[9]  = _AUDIO_BUF_LEN              # byte 9 controls audio buffer depth
    pkt[10] = pkt_ctr & 0xFF

    # State section
    pkt[11] = 0x10 | 0x80                 # 0x90 — state section header
    pkt[12] = 63
    pkt[13:76] = state_bytes[:63]

    # Haptics section (zeros = no haptics)
    pkt[76] = 0x12 | 0x80                 # 0x92 — haptics section header
    pkt[77] = 64
    # pkt[78:142] already zeros

    # Speaker audio section
    pkt[142] = 0x13 | 0x80               # 0x93 — speaker section header
    pkt[143] = 200
    pkt[144:344] = opus_bytes[:200]

    # pkt[344:394] = zeros (padding before CRC)
    _append_bt_audio_crc(pkt)            # fills pkt[394:398]
    return bytes(pkt)


# ── Streaming helpers ─────────────────────────────────────────────────────────

try:
    import numpy as np
    import sounddevice as sd
    _HAS_SD = True
except ImportError:
    _HAS_SD = False


def _sine_pcm(freq: float, amplitude: float, offset_frames: int) -> bytes:
    """Generate one 480-frame (10 ms) chunk of a stereo sine tone as int16."""
    if not _HAS_SD:
        import struct as _s
        return b"\x00" * (_OPUS_FRAME_SAMPLES * _OPUS_CHANNELS * 2)
    t = (offset_frames + np.arange(_OPUS_FRAME_SAMPLES)) / _OPUS_SAMPLE_RATE
    tone = (amplitude * np.sin(2 * math.pi * freq * t)).astype(np.float32)
    stereo = np.column_stack([tone, tone])
    return (stereo * 32767).astype(np.int16).tobytes()


class BTAudioStream:
    """Stream audio to the DualSense speaker over Bluetooth via report 0x36.

    Two audio sources are supported:

    * ``source="tone"`` — generate a continuous sine tone (default).
    * ``source="mic"``  — capture from a sounddevice input device and play
      through the DualSense speaker (requires sounddevice + numpy).

    Usage::

        stream = BTAudioStream(
            send_fn=controller.write_bt_audio_frame,
            speaker_vol=200,
        )
        stream.start(source="tone", freq=440.0)
        time.sleep(5)
        stream.stop()

    Args:
        send_fn:     Callable ``(opus_bytes, state_bytes) → None``.
                     Typically ``controller.write_bt_audio_frame``.
        speaker_vol: Speaker volume embedded in each report's state section.
        rgb:         Lightbar colour ``(r, g, b)`` embedded in each report.
    """

    def __init__(
        self,
        send_fn: Callable[[bytes, bytes], None],
        speaker_vol: int = 200,
        rgb: tuple = (0, 0, 200),
    ) -> None:
        self._send        = send_fn
        self._speaker_vol = speaker_vol
        self._rgb         = rgb
        self._thread: Optional[threading.Thread] = None
        self._stop_ev     = threading.Event()

    def start(
        self,
        source: str = "tone",
        freq: float = 440.0,
        amplitude: float = 0.6,
        in_device: "int | None" = None,
    ) -> None:
        """Start the streaming thread.

        Args:
            source:    ``"tone"`` or ``"mic"``.
            freq:      Sine frequency in Hz (only for source="tone").
            amplitude: Amplitude 0–1 (only for source="tone").
            in_device: sounddevice input device index (only for source="mic").
        """
        if self._thread is not None:
            return
        self._stop_ev.clear()
        if source == "mic":
            self._thread = threading.Thread(
                target=self._mic_loop,
                args=(in_device,),
                daemon=True,
            )
        else:
            self._thread = threading.Thread(
                target=self._tone_loop,
                args=(freq, amplitude),
                daemon=True,
            )
        self._thread.start()

    def stop(self) -> None:
        """Signal the stream to stop and wait for the thread to exit."""
        self._stop_ev.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _state(self) -> bytes:
        r, g, b = self._rgb
        return make_bt_state_bytes(self._speaker_vol, r, g, b)

    def _tone_loop(self, freq: float, amplitude: float) -> None:
        """Generate and stream a sine tone until stopped."""
        try:
            enc = _OpusEncoder()
        except Exception as exc:
            print(f"\n  [bt_audio] Opus init failed: {exc}")
            return

        state      = self._state()
        frame_idx  = 0
        frame_dur  = _OPUS_FRAME_SAMPLES / _OPUS_SAMPLE_RATE  # 0.01 s
        next_send  = time.monotonic()

        while not self._stop_ev.is_set():
            pcm  = _sine_pcm(freq, amplitude, frame_idx)
            opus = enc.encode(pcm)
            self._send(opus, state)
            frame_idx += _OPUS_FRAME_SAMPLES
            next_send += frame_dur
            sleep_dur  = next_send - time.monotonic()
            if sleep_dur > 0:
                time.sleep(sleep_dur)

    def _mic_loop(self, in_device: "int | None") -> None:
        """Capture from a mic, encode, and stream to DualSense speaker."""
        if not _HAS_SD:
            print("  [bt_audio] sounddevice not installed")
            return
        try:
            enc = _OpusEncoder()
        except Exception as exc:
            print(f"\n  [bt_audio] Opus init failed: {exc}")
            return

        try:
            info = sd.query_devices(in_device, kind="input")
            in_sr = int(info["default_samplerate"])
            in_ch = min(int(info["max_input_channels"]), 2)
        except Exception:
            in_sr, in_ch = 44100, 1

        # Resample mic → 48 kHz if needed
        need_resample = (in_sr != _OPUS_SAMPLE_RATE)
        if need_resample:
            try:
                import soxr
                resampler = soxr.ResampleStream(
                    in_sr, _OPUS_SAMPLE_RATE, in_ch, quality="MQ"
                )
            except ImportError:
                print(
                    "  [bt_audio] soxr not installed; mic will play at "
                    "wrong pitch (install with: pip install soxr)"
                )
                resampler = None
                need_resample = False

        pcm_buf = bytearray()
        lock    = threading.Lock()
        frame_bytes = _OPUS_FRAME_SAMPLES * _OPUS_CHANNELS * 2  # int16 stereo

        def _cb(indata, frames, _t, _status):
            mono = indata[:, 0] if indata.ndim > 1 else indata.ravel()
            stereo = np.column_stack([mono, mono]).astype(np.float32)
            # Resample if input rate differs from 48 kHz
            if need_resample and resampler is not None:
                stereo = resampler.resample_chunk(stereo)
            pcm_int16 = (np.clip(stereo, -1.0, 1.0) * 32767).astype(np.int16)
            with lock:
                pcm_buf.extend(pcm_int16.tobytes())

        state = self._state()
        with sd.InputStream(
            samplerate=in_sr, channels=in_ch,
            dtype="float32", device=in_device,
            blocksize=512, callback=_cb
        ):
            frame_dur = _OPUS_FRAME_SAMPLES / _OPUS_SAMPLE_RATE
            next_send = time.monotonic() + frame_dur * 2  # prefill buffer

            while not self._stop_ev.is_set():
                with lock:
                    available = len(pcm_buf)
                if available >= frame_bytes:
                    with lock:
                        chunk = bytes(pcm_buf[:frame_bytes])
                        del pcm_buf[:frame_bytes]
                    opus = enc.encode(chunk)
                    self._send(opus, state)
                    next_send += frame_dur
                sleep_dur = min(frame_dur * 0.5, next_send - time.monotonic())
                if sleep_dur > 0:
                    time.sleep(sleep_dur)
