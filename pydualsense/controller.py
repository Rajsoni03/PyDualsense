"""
DualSense — main controller class.

Typical usage::

    from pydualsense import DualSense, TriggerMode
    from pydualsense.features.triggers import TriggerEffect

    ds = DualSense()
    ds.connect()

    # Read one snapshot
    state = ds.read()
    print(state.left_stick, state.buttons.cross)

    # Output
    ds.set_led(0, 0, 255)
    ds.set_rumble(128, 128)
    ds.set_trigger_effect("right", TriggerEffect.weapon())

    ds.disconnect()

For a continuous event loop::

    def on_state(state):
        if state.buttons.cross:
            print("Cross!")

    ds.listen(on_state)   # blocking; Ctrl-C to stop
"""

import threading
import time
from typing import Callable, Optional

from .transport.hid_transport import HIDTransport
from .transport.discovery import find_controller, ControllerInfo
from .protocol.input_report import InputState, parse_input_report
from .protocol.output_report import OutputReport
from .protocol.constants import (
    TriggerMode, PlayerLED, MicLED,
    DUALSENSE_VID, SUPPORTED_PIDS,
    BT_INPUT_REPORT_LEN,
)
from .protocol.crc import append_feature_report_crc
from .features.triggers import TriggerEffect
from .features.bt_audio import (
    BTAudioStream, build_bt_audio_report, make_bt_state_bytes,
    _HAS_OPUS,
)

# Feature report 0x80 — firmware test/audio interface
# (matching daidr/dualsense-tester ds.util.ts controlWaveOut)
_FEAT_REPORT_ID   = 0x80
_FEAT_REPORT_SIZE = 63      # data bytes (excl. report-ID byte prepended by hidapi)
_AUDIO_DEVICE_ID  = 6       # DualSenseTestDeviceId.AUDIO
_ACTION_CALIB     = 4       # DualSenseTestActionId.BUILTIN_MIC_CALIB_DATA_VERIFY
_ACTION_WAVEOUT   = 2       # DualSenseTestActionId.WAVEOUT_CTRL


class DualSense:
    """PS5 DualSense controller interface."""

    def __init__(self):
        self._transport = HIDTransport()
        self._output = OutputReport()
        self._state: Optional[InputState] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._bt_audio_seq: int = 0
        self._bt_pkt_ctr:   int = 0
        self._bt_stream: Optional[BTAudioStream] = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, serial: Optional[str] = None) -> None:
        """Connect to the first available DualSense controller.

        Args:
            serial: Optional serial number to target a specific device.

        Raises:
            RuntimeError: if no DualSense is found.
        """
        info = find_controller(serial)
        if info is None:
            raise RuntimeError(
                "No DualSense controller found.  "
                "Ensure the controller is paired and connected over Bluetooth."
            )
        self._transport.open_path(info.path)
        # Default light bar blue (player-1 convention)
        self.set_led(0, 0, 64)
        self.set_player_leds(PlayerLED.player(1))

    def disconnect(self) -> None:
        """Stop the event loop (if running) and close the HID device."""
        self.stop()
        self.stop_bt_speaker()
        self._transport.close()

    # ── Reading ───────────────────────────────────────────────────────────────

    def read(self) -> InputState:
        """Block until one HID input report arrives and return parsed state."""
        raw = self._transport.read(BT_INPUT_REPORT_LEN, timeout_ms=1000)
        if not raw:
            raise TimeoutError("No input report received within 1 s")
        state = parse_input_report(raw)
        with self._lock:
            self._state = state
        return state

    @property
    def state(self) -> Optional[InputState]:
        """Most recent InputState (None until first :meth:`read` or callback)."""
        with self._lock:
            return self._state

    # ── Continuous event loop ─────────────────────────────────────────────────

    def listen(self, callback: Callable[[InputState], None],
               poll_interval: float = 0.001) -> None:
        """Start a blocking read loop, calling *callback* on each new state.

        Press Ctrl-C to stop.

        Args:
            callback:      Called with the latest InputState on every poll.
            poll_interval: Seconds to sleep between unsuccessful reads.
        """
        self._running = True
        try:
            while self._running:
                raw = self._transport.read(BT_INPUT_REPORT_LEN, timeout_ms=16)
                if raw:
                    state = parse_input_report(raw)
                    with self._lock:
                        self._state = state
                    callback(state)
                else:
                    time.sleep(poll_interval)
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False

    def listen_async(self, callback: Callable[[InputState], None]) -> None:
        """Start the event loop in a background daemon thread."""
        self._thread = threading.Thread(
            target=self.listen, args=(callback,), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the event loop to stop."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    # ── Output helpers ────────────────────────────────────────────────────────

    def _send(self) -> None:
        self._transport.write(self._output.build())

    def set_rumble(self, right: int = 0, left: int = 0) -> None:
        """Set ERM rumble motors.  right = small (HF), left = large (LF), 0–255."""
        self._output.set_rumble(right, left)
        self._send()

    def stop_rumble(self) -> None:
        """Stop all rumble."""
        self.set_rumble(0, 0)

    def set_trigger_effect(self, side: str, effect: TriggerEffect) -> None:
        """Apply an adaptive trigger effect.

        Args:
            side:   ``"left"`` / ``"l2"`` or ``"right"`` / ``"r2"``.
            effect: A :class:`TriggerEffect` instance (e.g. ``TriggerEffect.weapon()``).
        """
        mode_name = effect.mode.name.lower()
        method = getattr(self._output, f"set_trigger_{mode_name}", None)
        if method is None:
            # Fallback: use generic _set_trigger via built-in methods
            _dispatch = {
                TriggerMode.OFF:            self._output.set_trigger_off,
                TriggerMode.FEEDBACK:       self._output.set_trigger_feedback,
                TriggerMode.WEAPON:         self._output.set_trigger_weapon,
                TriggerMode.VIBRATION:      self._output.set_trigger_vibration,
                TriggerMode.SLOPE_FEEDBACK: self._output.set_trigger_slope,
                TriggerMode.RIGID:          self._output.set_trigger_rigid,
                TriggerMode.MULTI_POS:      self._output.set_trigger_multi_pos,
            }
            fn = _dispatch.get(effect.mode)
            if fn is None:
                raise ValueError(f"Unsupported trigger mode: {effect.mode!r}")
            fn(side, **effect.params)
        else:
            method(side, **effect.params)
        self._send()

    def set_trigger_off(self, side: str = "both") -> None:
        """Disable adaptive effects on one or both triggers."""
        sides = ["left", "right"] if side == "both" else [side]
        for s in sides:
            self._output.set_trigger_off(s)
        self._send()

    def set_led(self, r: int, g: int, b: int) -> None:
        """Set the light-bar RGB colour (each 0–255)."""
        self._output.set_lightbar(r, g, b)
        self._send()

    def set_player_leds(self, mask) -> None:
        """Set player-indicator LED bitmask.  Use :class:`PlayerLED` flags."""
        self._output.set_player_leds(int(mask))
        self._send()

    def set_mic_led(self, mode: MicLED = MicLED.OFF) -> None:
        """Set the microphone-mute indicator LED."""
        self._output.set_mic_led(mode)
        self._send()

    def set_speaker_volume(self, volume: int) -> None:
        self._output.set_speaker_volume(volume)
        self._send()

    def set_headphone_volume(self, volume: int) -> None:
        self._output.set_headphone_volume(volume)
        self._send()

    def set_mic_volume(self, volume: int) -> None:
        self._output.set_mic_volume(volume)
        self._send()

    # ── Audio waveout (feature report 0x80) ───────────────────────────────────

    def _send_feature_report(self, payload: bytes) -> None:
        """Pad *payload* to _FEAT_REPORT_SIZE, append BT CRC if needed, and send."""
        data = bytearray(_FEAT_REPORT_SIZE)
        data[:len(payload)] = payload
        if self._transport.is_bluetooth:
            append_feature_report_crc(_FEAT_REPORT_ID, data)
        try:
            self._transport.send_feature_report(_FEAT_REPORT_ID, bytes(data))
        except Exception:
            pass  # feature reports may not be supported on all platforms/firmwares

    def enable_speaker_audio(self) -> None:
        """Enable the built-in speaker audio path via the firmware test interface.

        Mirrors ``controlWaveOut(device, true, 'speaker')`` from the reference
        implementation (daidr/dualsense-tester ds.util.ts).  Must be called
        after setting the speaker volume and before playing audio through the
        OS audio device.
        """
        # Step 1: configure speaker routing (params[2] = 8)
        params = bytearray(20)
        params[2] = 8
        self._send_feature_report(bytes([_AUDIO_DEVICE_ID, _ACTION_CALIB]) + bytes(params))
        time.sleep(0.02)
        # Step 2: enable waveout [enable=1, 1, 0]
        self._send_feature_report(bytes([_AUDIO_DEVICE_ID, _ACTION_WAVEOUT, 1, 1, 0]))

    def enable_headphone_audio(self) -> None:
        """Enable the headphone jack audio path via the firmware test interface.

        Mirrors ``controlWaveOut(device, true, 'headphone')``.
        """
        # Step 1: configure headphone routing (params[4]=4, params[6]=6)
        params = bytearray(20)
        params[4] = 4
        params[6] = 6
        self._send_feature_report(bytes([_AUDIO_DEVICE_ID, _ACTION_CALIB]) + bytes(params))
        time.sleep(0.02)
        # Step 2: enable waveout
        self._send_feature_report(bytes([_AUDIO_DEVICE_ID, _ACTION_WAVEOUT, 1, 1, 0]))

    def disable_audio(self) -> None:
        """Disable the audio waveout — mirrors ``controlWaveOut(device, false)``."""
        self._send_feature_report(bytes([_AUDIO_DEVICE_ID, _ACTION_WAVEOUT, 0, 1, 0]))

    # ── Bluetooth audio (HID report 0x36) ────────────────────────────────────

    def write_bt_audio_frame(self, opus_bytes: bytes, state_bytes: bytes) -> None:
        """Send one 10 ms Opus frame to the DualSense speaker over BT.

        Builds a 398-byte report 0x36 with CRC and writes it to the HID
        interrupt channel via hidapi.

        Args:
            opus_bytes:  200-byte CBR Opus packet (padded to 200 if shorter).
            state_bytes: 63-byte state from :func:`make_bt_state_bytes`.
        """
        pkt = build_bt_audio_report(
            opus_bytes, state_bytes,
            self._bt_audio_seq, self._bt_pkt_ctr,
        )
        self._bt_audio_seq = (self._bt_audio_seq + 1) & 0x0F
        self._bt_pkt_ctr   = (self._bt_pkt_ctr   + 1) & 0xFF
        self._transport.write(pkt)

    def stream_bt_speaker(
        self,
        source: str = "tone",
        freq: float = 440.0,
        amplitude: float = 0.6,
        duration: Optional[float] = None,
        in_device: "Optional[int]" = None,
    ) -> "BTAudioStream":
        """Start streaming audio to the DualSense built-in speaker over BT.

        Uses HID report 0x36 with Opus-encoded audio.  Requires:
          - cffi (``pip install cffi``)
          - libopus (``brew install opus`` on macOS)

        Args:
            source:    ``"tone"`` — sine wave tone, or
                       ``"mic"``  — capture from *in_device* and play back.
            freq:      Tone frequency Hz (source="tone" only).
            amplitude: Tone amplitude 0–1 (source="tone" only).
            duration:  Stop automatically after this many seconds (None = run
                       until :meth:`stop_bt_speaker` is called).
            in_device: Input device index for source="mic".

        Returns:
            The :class:`BTAudioStream` instance (already started).
        """
        if not _HAS_OPUS:
            raise RuntimeError(
                "cffi or libopus not available.  "
                "pip install cffi && brew install opus"
            )
        if self._bt_stream is not None:
            self._bt_stream.stop()
        # Extract current lightbar colour from the output buffer
        r = int(self._output._buf[47])
        g = int(self._output._buf[48])
        b = int(self._output._buf[49])
        stream = BTAudioStream(
            send_fn=self.write_bt_audio_frame,
            speaker_vol=max(0, min(255, int(self._output._buf[8]))),
            rgb=(r, g, b),
        )
        stream.start(source=source, freq=freq, amplitude=amplitude,
                     in_device=in_device)
        self._bt_stream = stream
        if duration is not None:
            def _auto_stop():
                time.sleep(duration)
                stream.stop()
            threading.Thread(target=_auto_stop, daemon=True).start()
        return stream

    def stop_bt_speaker(self) -> None:
        """Stop BT speaker streaming if running."""
        if self._bt_stream is not None:
            self._bt_stream.stop()
            self._bt_stream = None

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
