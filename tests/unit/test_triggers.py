"""Unit tests for TriggerEffect factory methods."""

import pytest
from pydualsense.features.triggers import TriggerEffect
from pydualsense.protocol.constants import TriggerMode


class TestTriggerEffectFactories:
    def test_off(self):
        e = TriggerEffect.off()
        assert e.mode == TriggerMode.OFF
        assert e.params == {}

    def test_feedback(self):
        e = TriggerEffect.feedback(start=60, force=180)
        assert e.mode == TriggerMode.FEEDBACK
        assert e.params["start"] == 60
        assert e.params["force"] == 180

    def test_feedback_defaults(self):
        e = TriggerEffect.feedback()
        assert "start" in e.params
        assert "force" in e.params

    def test_weapon(self):
        e = TriggerEffect.weapon(start=30, end=100, force=200)
        assert e.mode == TriggerMode.WEAPON
        assert e.params["start"] == 30
        assert e.params["end"] == 100
        assert e.params["force"] == 200

    def test_vibration(self):
        e = TriggerEffect.vibration(position=0, amplitude=200, frequency=30)
        assert e.mode == TriggerMode.VIBRATION
        assert e.params["amplitude"] == 200
        assert e.params["frequency"] == 30

    def test_slope(self):
        e = TriggerEffect.slope(start=0, end=255, start_force=0, end_force=255)
        assert e.mode == TriggerMode.SLOPE_FEEDBACK

    def test_rigid(self):
        e = TriggerEffect.rigid()
        assert e.mode == TriggerMode.RIGID
        assert e.params == {}

    def test_multi_pos(self):
        e = TriggerEffect.multi_pos([50, 120, 200], [180, 180, 180])
        assert e.mode == TriggerMode.MULTI_POS
        assert e.params["positions"] == [50, 120, 200]
        assert e.params["forces"] == [180, 180, 180]

    def test_repr(self):
        e = TriggerEffect.feedback(start=10, force=100)
        r = repr(e)
        assert "FEEDBACK" in r
