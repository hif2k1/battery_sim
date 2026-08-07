"""Tests for the battery_sim select platform."""
from homeassistant.core import State

from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.battery_sim.const import (
    DEFAULT_MODE,
    DISCHARGE_ONLY,
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


async def test_mode_exposes_internal_key_as_attribute(hass, setup_battery):
    await setup_battery()

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": MODE_SELECT_ID, "option": "Discharge only"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(MODE_SELECT_ID)
    assert state.state == "Discharge only"
    assert state.attributes["battery_mode"] == DISCHARGE_ONLY


async def test_mode_restored_from_attribute(hass, setup_battery):
    mock_restore_cache(
        hass,
        [
            State(
                MODE_SELECT_ID,
                "Discharge only",
                {"battery_mode": DISCHARGE_ONLY},
            )
        ],
    )

    _entry, handle = await setup_battery()

    assert handle._battery_mode == DISCHARGE_ONLY
    assert hass.states.get(MODE_SELECT_ID).state == "Discharge only"


async def test_mode_restored_from_state_without_attribute(hass, setup_battery):
    """States stored before the attribute existed still restore."""
    mock_restore_cache(hass, [State(MODE_SELECT_ID, "Force discharge")])

    _entry, handle = await setup_battery()

    assert handle._battery_mode == FORCE_DISCHARGE
    assert hass.states.get(MODE_SELECT_ID).state == "Force discharge"


async def test_invalid_restored_mode_falls_back_to_default(
    hass, setup_battery, caplog
):
    mock_restore_cache(hass, [State(MODE_SELECT_ID, "Not a real mode")])

    _entry, handle = await setup_battery()

    assert handle._battery_mode == DEFAULT_MODE
    assert "Ignoring invalid restored battery mode" in caplog.text


async def test_unavailable_restored_mode_falls_back_to_default(hass, setup_battery):
    mock_restore_cache(hass, [State(MODE_SELECT_ID, "unavailable")])

    _entry, handle = await setup_battery()

    assert handle._battery_mode == DEFAULT_MODE
