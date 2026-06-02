"""Unit tests for deadzone utilities."""

import math
import pytest
from pydualsense.utils.deadzone import (
    apply_deadzone,
    apply_deadzone_circular,
    apply_deadzone_square,
)


class TestApplyDeadzone:
    def test_inside_deadzone(self):
        assert apply_deadzone(0.05, 0.10) == 0.0

    def test_outside_deadzone_positive(self):
        result = apply_deadzone(1.0, 0.10)
        assert abs(result - 1.0) < 1e-6

    def test_outside_deadzone_negative(self):
        result = apply_deadzone(-1.0, 0.10)
        assert abs(result - (-1.0)) < 1e-6

    def test_rescaling(self):
        # At exactly threshold the output should be 0, at 1.0 output should be 1.0
        threshold = 0.15
        assert apply_deadzone(threshold, threshold) == 0.0
        assert abs(apply_deadzone(1.0, threshold) - 1.0) < 1e-6

    def test_zero_input(self):
        assert apply_deadzone(0.0, 0.10) == 0.0

    def test_negative_just_inside(self):
        assert apply_deadzone(-0.09, 0.10) == 0.0


class TestApplyDeadzoneCircular:
    def test_inside_circle(self):
        x, y = apply_deadzone_circular(0.05, 0.05, 0.10)
        assert x == 0.0
        assert y == 0.0

    def test_full_right(self):
        x, y = apply_deadzone_circular(1.0, 0.0, 0.10)
        assert abs(x - 1.0) < 1e-6
        assert abs(y) < 1e-6

    def test_diagonal_preserved(self):
        x, y = apply_deadzone_circular(0.707, 0.707, 0.10)
        magnitude = math.sqrt(x * x + y * y)
        assert magnitude > 0.0

    def test_zero_input(self):
        x, y = apply_deadzone_circular(0.0, 0.0, 0.10)
        assert x == 0.0
        assert y == 0.0

    def test_direction_preserved(self):
        x, y = apply_deadzone_circular(0.8, 0.6, 0.10)
        # Direction should be same as input (0.8, 0.6)
        orig_angle = math.atan2(0.6, 0.8)
        new_angle  = math.atan2(y, x)
        assert abs(orig_angle - new_angle) < 1e-5
