"""Tests for the battery_sim select platform."""
from custom_components.battery_sim.const import (
    DEFAULT_MODE,
    FORCE_DISCHARGE,
    OVERRIDE_CHARGING,
    PAUSE_BATTERY,
)

from .common import MODE_SELECT_ID


async def test_mode_select_created_with_options(hass, setup_battery):
    await setup_battery()

    state = hass.states.get(MODE_SELECT_ID)
    assert state is not None
    assert state.state == "Default mode"
    assert state.attributes["options"] == [
        "Default mode",
        "Force charge",
        "Pause battery",
        "Force discharge",
        "Charge only",
        "Discharge only",
    ]


async def test_selecting_mode_updates_handle(hass, setup_battery):
    _entry, handle = await setup_battery()
    assert handle._battery_mode == DEFAULT_MODE

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": MODE_SELECT_ID, "option": "Force charge"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert handle._battery_mode == OVERRIDE_CHARGING
    assert hass.states.get(MODE_SELECT_ID).state == "Force charge"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": MODE_SELECT_ID, "option": "Force discharge"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert handle._battery_mode == FORCE_DISCHARGE

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": MODE_SELECT_ID, "option": "Pause battery"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert handle._battery_mode == PAUSE_BATTERY


async def test_invalid_option_is_ignored(hass, setup_battery, caplog):
    _entry, handle = await setup_battery()

    entity = hass.data["entity_components"]["select"].get_entity(MODE_SELECT_ID)
    await entity.async_select_option("Not a real mode")

    assert handle._battery_mode == DEFAULT_MODE
    assert "Invalid option selected" in caplog.text
