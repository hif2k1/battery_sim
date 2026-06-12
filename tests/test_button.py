"""Tests for the battery_sim button platform."""
import pytest

from custom_components.battery_sim.const import (
    ATTR_ENERGY_SAVED,
    GRID_IMPORT_SIM,
)

from .common import (
    EXPORT_SENSOR_ID,
    IMPORT_SENSOR_ID,
    KWH_ATTRIBUTES,
    RESET_BUTTON_ID,
)


async def test_reset_button_created(hass, setup_battery):
    await setup_battery()
    assert hass.states.get(RESET_BUTTON_ID) is not None


async def test_pressing_reset_button_resets_battery(hass, setup_battery):
    hass.states.async_set(IMPORT_SENSOR_ID, "123.4", KWH_ATTRIBUTES)
    hass.states.async_set(EXPORT_SENSOR_ID, "55.5", KWH_ATTRIBUTES)
    _entry, handle = await setup_battery()

    handle._charge_state = 8.2
    handle._sensors[ATTR_ENERGY_SAVED] = 7.0

    await hass.services.async_call(
        "button", "press", {"entity_id": RESET_BUTTON_ID}, blocking=True
    )
    await hass.async_block_till_done()

    assert handle._charge_state == pytest.approx(5.0)
    assert handle._sensors[ATTR_ENERGY_SAVED] == 0.0
    # Simulated meters rebase onto the live readings.
    assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(123.4)
