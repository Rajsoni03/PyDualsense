"""
Integration tests — require a physical DualSense controller connected over BT.

Run only when hardware is available:

    pytest tests/integration/ -v --hardware
"""

import pytest
import time


def pytest_addoption(parser):
    parser.addoption("--hardware", action="store_true",
                     help="Run hardware-in-the-loop tests")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--hardware", default=False):
        skip = pytest.mark.skip(reason="Requires --hardware flag and physical controller")
        for item in items:
            if "integration" in str(item.fspath):
                item.add_marker(skip)


@pytest.fixture
def ds():
    from pydualsense import DualSense
    controller = DualSense()
    controller.connect()
    yield controller
    controller.disconnect()


def test_connect_and_read(ds):
    state = ds.read()
    assert state is not None
    assert 0 <= state.l2 <= 255
    assert 0 <= state.r2 <= 255


def test_lightbar(ds):
    ds.set_led(255, 0, 0)
    time.sleep(0.2)
    ds.set_led(0, 0, 255)
    time.sleep(0.2)


def test_rumble(ds):
    ds.set_rumble(100, 100)
    time.sleep(0.5)
    ds.stop_rumble()


def test_trigger_feedback(ds):
    from pydualsense.features.triggers import TriggerEffect
    ds.set_trigger_effect("right", TriggerEffect.feedback(start=50, force=150))
    time.sleep(1.0)
    ds.set_trigger_off("both")


def test_battery_reads(ds):
    state = ds.read()
    assert 0 <= state.battery.level <= 100
