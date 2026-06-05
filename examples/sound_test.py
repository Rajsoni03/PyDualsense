#!/usr/bin/env python3
"""
sound_test.py — Interactive audio test for the DualSense controller.

IMPORTANT: The DualSense speaker and microphone are only accessible when
connected via USB cable.  Over Bluetooth, macOS only binds the HID
(controller) profile — the USB Audio Class device (speaker + mic) is never
registered and sounddevice cannot see it.

Connect with a USB-C cable before running this script.

Four sequential tests, each with a distinct light-bar colour:

  1. Speaker test    (blue)   — ramp 0 → 80 → 0, live volume bar
  2. Mic test        (red)    — live VU meter; blow into the mic to see it move
  3. Headphone test  (green)  — detect 3.5 mm jack, ramp headphone volume
  4. Headset mic     (yellow) — detect headset mic, live VU meter

Install audio dependencies:
    pip install sounddevice numpy

Press Cross (✕) to skip the current test.
Press Options to quit early.
"""

import os
import sys
import math
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydualsense import DualSense
from pydualsense.protocol.constants import MicLED
from pydualsense.features.audio import (
    HEADPHONE_VOLUME_MAX,
    MIC_VOLUME_MAX,
)
from pydualsense.features.bt_audio import _HAS_OPUS, BTAudioStream

SPEAKER_TEST_MAX = 80   # volume cap for speaker ramp (0–255)
BAR_WIDTH        = 36

try:
    import numpy as np
    import sounddevice as sd
    _AUDIO = True
except ImportError:
    _AUDIO = False


# ── DualSense audio device detection ─────────────────────────────────────────

_DS_KEYWORDS = ("dualsense", "dual sense", "wireless controller")


def _find_dualsense_output() -> "int | None":
    if not _AUDIO:
        return None
    try:
        for i, dev in enumerate(sd.query_devices()):
            if any(k in dev["name"].lower() for k in _DS_KEYWORDS) \
                    and dev["max_output_channels"] > 0:
                return i
    except Exception:
        pass
    return None


def _find_dualsense_input() -> "int | None":
    if not _AUDIO:
        return None
    try:
        for i, dev in enumerate(sd.query_devices()):
            if any(k in dev["name"].lower() for k in _DS_KEYWORDS) \
                    and dev["max_input_channels"] > 0:
                return i
    except Exception:
        pass
    return None


def _list_audio_devices() -> None:
    if not _AUDIO:
        return
    print("Audio devices visible to sounddevice:")
    for i, d in enumerate(sd.query_devices()):
        flag = " <-- DualSense" \
               if any(k in d["name"].lower() for k in _DS_KEYWORDS) else ""
        print(f"  [{i:2d}] in={d['max_input_channels']} "
              f"out={d['max_output_channels']} "
              f"sr={int(d['default_samplerate']):>6}  "
              f"{d['name']}{flag}")
    print()


# ── Terminal bar helpers ──────────────────────────────────────────────────────

def _vol_bar(vol: int, max_vol: int) -> str:
    filled = round(vol * BAR_WIDTH / max_vol) if max_vol else 0
    return "█" * max(0, min(BAR_WIDTH, filled)) + \
           "░" * max(0, BAR_WIDTH - min(BAR_WIDTH, filled))


def _vu_bar(rms: float, max_rms: float) -> str:
    filled = round(min(rms / max_rms, 1.0) * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def _print_vol(vol: int, max_vol: int) -> None:
    print(f"\r  Vol  [{_vol_bar(vol, max_vol)}] {vol:3}/{max_vol}",
          end="", flush=True)


def _print_vu(rms: float, max_rms: float) -> None:
    pct = round(min(rms / max_rms, 1.0) * 100)
    print(f"\r  Mic  [{_vu_bar(rms, max_rms)}] {pct:3}%  (raw={rms:.4f})",
          end="", flush=True)


# ── Continuous sine tone ──────────────────────────────────────────────────────

class _ToneStream:
    def __init__(self, freq: float = 440.0, amplitude: float = 0.3,
                 device: "int | None" = None):
        self._freq = freq
        self._amplitude = amplitude
        self._device = device
        self._stream = None

    def start(self) -> None:
        if not _AUDIO or self._stream is not None:
            return
        try:
            info = sd.query_devices(self._device, kind="output")
            sr   = int(info["default_samplerate"])
            ch   = min(int(info["max_output_channels"]), 2)
        except Exception:
            sr, ch = 44100, 1

        freq = self._freq
        amp  = self._amplitude
        ref  = [0]

        def _cb(outdata, frames, _t, _s):
            t = (ref[0] + np.arange(frames)) / sr
            tone = (amp * np.sin(2 * math.pi * freq * t)).astype(np.float32)
            outdata[:] = np.column_stack([tone] * ch)
            ref[0] = (ref[0] + frames) % sr

        try:
            self._stream = sd.OutputStream(
                samplerate=sr, channels=ch,
                callback=_cb, device=self._device)
            self._stream.start()
            print(f"  [tone] {freq:.0f} Hz → device [{self._device}]")
        except Exception as exc:
            print(f"\n  [tone error] {exc}")
            self._stream = None

    def stop(self) -> None:
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()


# ── Volume ramp with live bar ─────────────────────────────────────────────────

def _ramp_with_bar(setter, target: int, skip_flag: threading.Event,
                   steps: int = 16, delay: float = 0.13) -> None:
    for i in list(range(steps + 1)) + list(range(steps - 1, -1, -1)):
        if skip_flag.is_set():
            break
        vol = round(i * target / steps)
        setter(vol)
        _print_vol(vol, target)
        time.sleep(delay)
    setter(0)
    _print_vol(0, target)
    print()


# ── Mic VU meter ──────────────────────────────────────────────────────────────

def _vu_meter_loop(in_dev: "int | None", skip_flag: threading.Event,
                   duration: float = 12.0,
                   max_rms: float = 0.08) -> None:
    """Capture mic input and show a live VU bar.

    max_rms=0.08 means the bar fills at ~8% signal amplitude — sensitive
    enough to show normal speech and blowing.
    """
    if not _AUDIO:
        print("  (sounddevice not installed)")
        time.sleep(2.0)
        return

    if in_dev is None:
        print("  DualSense not found in audio devices — is it connected via USB?")
        print("  Available devices shown at startup. Skipping mic VU meter.")
        time.sleep(3.0)
        return

    rms_val = [0.0]

    def _cb(indata, _frames, _time, status):
        if status:
            pass  # don't crash on overflow/underrun
        ch_data = indata[:, 0] if indata.ndim > 1 else indata.ravel()
        rms_val[0] = float(np.sqrt(np.mean(ch_data.astype(np.float32) ** 2)))

    try:
        info = sd.query_devices(in_dev, kind="input")
        sr   = int(info["default_samplerate"])
        ch   = 1
        print(f"  [{in_dev}] {info['name']}  sr={sr} Hz")
        print(f"  Blow or speak into the mic (sensitivity 1/{max_rms:.2f}×):")
        with sd.InputStream(samplerate=sr, channels=ch,
                            dtype="float32", device=in_dev,
                            blocksize=512, callback=_cb):
            deadline = time.time() + duration
            while time.time() < deadline and not skip_flag.is_set():
                _print_vu(rms_val[0], max_rms)
                time.sleep(0.04)
    except Exception as exc:
        print(f"\n  [mic error] {type(exc).__name__}: {exc}")
        print("  Check System Settings → Privacy & Security → Microphone")

    print()


# ── Individual tests ──────────────────────────────────────────────────────────

def test_speaker(ds: DualSense, skip_flag: threading.Event,
                 out_dev: "int | None") -> None:
    print(f"  Ramping built-in speaker 0 → {SPEAKER_TEST_MAX} → 0")
    ds.set_led(0, 0, 200)
    ds.set_headphone_volume(0)
    ds.set_speaker_volume(SPEAKER_TEST_MAX)
    time.sleep(0.02)
    ds.enable_speaker_audio()
    with _ToneStream(freq=440.0, device=out_dev):
        _ramp_with_bar(ds.set_speaker_volume, SPEAKER_TEST_MAX, skip_flag)
    ds.disable_audio()
    ds.set_speaker_volume(0)


def test_mic(ds: DualSense, skip_flag: threading.Event,
             in_dev: "int | None") -> None:
    print("  Blow into the mic — live level meter (12 s, Cross to skip)")
    ds.set_led(200, 0, 0)
    ds.set_mic_led(MicLED.ON)
    ds.set_mic_volume(MIC_VOLUME_MAX)
    _vu_meter_loop(in_dev, skip_flag, duration=12.0)
    ds.set_mic_volume(0)
    ds.set_mic_led(MicLED.OFF)


def test_headphone(ds: DualSense, skip_flag: threading.Event,
                   connected: bool, out_dev: "int | None") -> None:
    if not connected:
        print("  No headphone detected — skipping.")
        return
    print("  Headphone detected.  Ramping headphone volume …")
    ds.set_led(0, 180, 0)
    ds.set_speaker_volume(0)
    ds.set_headphone_volume(HEADPHONE_VOLUME_MAX)
    time.sleep(0.02)
    ds.enable_headphone_audio()
    with _ToneStream(freq=880.0, device=out_dev):
        _ramp_with_bar(ds.set_headphone_volume, HEADPHONE_VOLUME_MAX, skip_flag)
    ds.disable_audio()
    ds.set_headphone_volume(0)


def test_headset_mic(ds: DualSense, skip_flag: threading.Event,
                     connected: bool, in_dev: "int | None") -> None:
    if not connected:
        print("  No headset mic detected — skipping.")
        return
    print("  Headset mic detected.  Blow into headset mic (12 s, Cross to skip)")
    ds.set_led(200, 200, 0)
    ds.set_mic_led(MicLED.BLINK)
    ds.set_mic_volume(MIC_VOLUME_MAX)
    _vu_meter_loop(in_dev, skip_flag, duration=12.0)
    ds.set_mic_volume(0)
    ds.set_mic_led(MicLED.OFF)


# ── Bluetooth speaker test (HID report 0x36 + Opus) ──────────────────────────

def test_speaker_bt(ds: DualSense, skip_flag: threading.Event) -> None:
    """Stream a 440 Hz tone to the DualSense built-in speaker over BT.

    Uses HID report 0x36 with Opus-encoded audio — bypasses the OS audio
    stack entirely (no sounddevice needed for playback).
    """
    print("  Streaming 440 Hz tone to DualSense speaker via BT (report 0x36)")
    print("  (requires cffi + libopus — pip install cffi && brew install opus)")
    ds.set_led(0, 0, 200)
    ds.set_speaker_volume(200)

    if not _HAS_OPUS:
        print("  cffi/libopus not available — cannot stream BT audio.")
        print("  Install with: pip install cffi && brew install opus")
        time.sleep(2.0)
        return

    stream = ds.stream_bt_speaker(source="tone", freq=440.0, amplitude=0.7)
    print("  Streaming…  Cross to stop early.")

    deadline = time.time() + 12.0
    while time.time() < deadline and not skip_flag.is_set():
        elapsed = 12.0 - (deadline - time.time())
        pct = min(1.0, elapsed / 12.0)
        filled = round(pct * BAR_WIDTH)
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)
        print(f"\r  BT  [{bar}] {elapsed:4.1f}s", end="", flush=True)
        time.sleep(0.05)

    print()
    ds.stop_bt_speaker()
    ds.set_speaker_volume(0)


def test_mic_bt(ds: DualSense, skip_flag: threading.Event,
                in_dev: "int | None") -> None:
    """Attempt BT mic test and explain the limitation."""
    print("  NOTE: DualSense microphone is NOT accessible over Bluetooth.")
    print("  The mic uses the USB Audio Class interface, which macOS only")
    print("  exposes when the controller is connected via USB cable.")
    print()
    print("  Alternative: capture from your Mac's microphone and stream it")
    print("  to the DualSense speaker over BT (HID report 0x36).")

    if not _AUDIO:
        print("  (sounddevice not installed — skipping)")
        time.sleep(3.0)
        return

    # Find any available input device (not DualSense — it's not visible over BT)
    mac_mic = None
    try:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0 and "dualsense" not in d["name"].lower():
                if "built-in" in d["name"].lower() or "macbook" in d["name"].lower():
                    mac_mic = i
                    break
        if mac_mic is None:
            # Fall back to default input
            mac_mic = sd.default.device[0] if hasattr(sd.default.device, '__getitem__') else None
    except Exception:
        pass

    if mac_mic is None:
        print("  No system microphone found — showing tone demo instead.")
        test_speaker_bt(ds, skip_flag)
        return

    try:
        mic_name = sd.query_devices(mac_mic)["name"]
    except Exception:
        mic_name = f"device [{mac_mic}]"

    print(f"  Capturing from: {mic_name}")
    print("  Speak into your Mac mic — audio will play through DualSense")
    print("  Cross to skip.\n")

    if not _HAS_OPUS:
        print("  cffi/libopus not available — install: pip install cffi && brew install opus")
        time.sleep(2.0)
        return

    ds.set_led(200, 0, 0)
    ds.set_mic_led(MicLED.ON)
    ds.set_speaker_volume(200)

    stream = ds.stream_bt_speaker(source="mic", in_device=mac_mic)

    deadline = time.time() + 12.0
    while time.time() < deadline and not skip_flag.is_set():
        elapsed = 12.0 - (deadline - time.time())
        pct = min(1.0, elapsed / 12.0)
        filled = round(pct * BAR_WIDTH)
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)
        print(f"\r  BT mic→speaker  [{bar}] {elapsed:4.1f}s", end="", flush=True)
        time.sleep(0.05)

    print()
    ds.stop_bt_speaker()
    ds.set_speaker_volume(0)
    ds.set_mic_led(MicLED.OFF)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not _AUDIO:
        print("ERROR: sounddevice/numpy not installed.")
        print("       source venv/bin/activate && pip install sounddevice numpy")
        sys.exit(1)

    _list_audio_devices()

    out_dev = _find_dualsense_output()
    in_dev  = _find_dualsense_input()

    if out_dev is None and in_dev is None:
        print("=" * 60)
        print("  DualSense not found as an OS audio device.")
        print()
        print("  Over Bluetooth, macOS does not expose the USB Audio Class")
        print("  interface — but BT speaker audio still works via HID report")
        print("  0x36 (Opus-encoded).  That test will run automatically.")
        print()
        print("  For mic VU meter and headphone tests, connect via USB-C.")
        print("=" * 60)
        print()
    else:
        if out_dev is not None:
            print(f"Audio output : [{out_dev}] {sd.query_devices(out_dev)['name']}")
        if in_dev is not None:
            print(f"Audio input  : [{in_dev}] {sd.query_devices(in_dev)['name']}")
        print()

    with DualSense() as ds:
        conn = "Bluetooth" if ds._transport.is_bluetooth else "USB"
        print(f"DualSense connected via {conn}")

        if ds._transport.is_bluetooth:
            print()
            print("  Bluetooth mode: speaker audio will use HID report 0x36 + Opus")
            if _HAS_OPUS:
                print("  Opus encoder ready — speaker test will stream via BT HID.")
            else:
                print("  NOTE: cffi/libopus not installed — speaker test unavailable.")
                print("        pip install cffi && brew install opus")
            print()

        print("  Cross (✕) = skip   Options = quit\n")

        skip_flag = threading.Event()
        quit_flag = threading.Event()

        state = ds.read()
        hp_connected  = state.headphone_connected
        mic_connected = state.mic_connected

        print(f"Headphone jack : {'detected' if hp_connected  else 'not detected'}")
        print(f"Headset mic    : {'detected' if mic_connected else 'not detected'}\n")

        if ds._transport.is_bluetooth:
            # Over BT the OS audio device is not visible — use HID report 0x36
            tests = [
                ("Speaker (BT)",    lambda: test_speaker_bt(ds, skip_flag)),
                ("Mic (BT)",        lambda: test_mic_bt(ds, skip_flag, in_dev)),
                ("Headphone",       lambda: test_headphone(ds, skip_flag, hp_connected, out_dev)),
                ("Headset mic",     lambda: test_headset_mic(ds, skip_flag, mic_connected, in_dev)),
            ]
        else:
            tests = [
                ("Speaker",     lambda: test_speaker(ds, skip_flag, out_dev)),
                ("Mic",         lambda: test_mic(ds, skip_flag, in_dev)),
                ("Headphone",   lambda: test_headphone(ds, skip_flag, hp_connected, out_dev)),
                ("Headset mic", lambda: test_headset_mic(ds, skip_flag, mic_connected, in_dev)),
            ]

        def _watch_buttons() -> None:
            while not quit_flag.is_set():
                try:
                    s = ds.read()
                    if s.buttons.cross:
                        skip_flag.set()
                    if s.buttons.options:
                        skip_flag.set()
                        quit_flag.set()
                except Exception:
                    break
                time.sleep(0.016)

        watcher = threading.Thread(target=_watch_buttons, daemon=True)
        watcher.start()

        for name, fn in tests:
            if quit_flag.is_set():
                break
            skip_flag.clear()
            print(f"=== {name} test ===")
            fn()
            time.sleep(0.4)

        ds.set_led(0, 0, 64)
        ds.set_mic_led(MicLED.OFF)
        ds.disable_audio()
        print("\nDone.")


if __name__ == "__main__":
    main()
