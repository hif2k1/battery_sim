"""Tests for the battery_sim switch platform."""
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import State

from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.battery_sim.const import PAUSE_BATTERY

from .common import PAUSE_SWITCH_ID


async def test_pause_switch_created_off(hass, setup_battery):
    _entry, handle = await setup_battery()

    state = hass.states.get(PAUSE_SWITCH_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert handle._switches[PAUSE_BATTERY] is False


async def test_pause_switch_turn_on_and_off(hass, setup_battery):
    _entry, handle = await setup_battery()

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": PAUSE_SWITCH_ID}, blocking=True
    )
    await hass.async_block_till_done()

    assert handle._switches[PAUSE_BATTERY] is True
    assert hass.states.get(PAUSE_SWITCH_ID).state == STATE_ON

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": PAUSE_SWITCH_ID}, blocking=True
    )
    await hass.async_block_till_done()

    assert handle._switches[PAUSE_BATTERY] is False
    assert hass.states.get(PAUSE_SWITCH_ID).state == STATE_OFF


async def test_pause_switch_restored_on(hass, setup_battery):
    mock_restore_cache(hass, [State(PAUSE_SWITCH_ID, STATE_ON)])

    _entry, handle = await setup_battery()

    assert handle._switches[PAUSE_BATTERY] is True
    assert hass.states.get(PAUSE_SWITCH_ID).state == STATE_ON


async def test_pause_switch_restored_off(hass, setup_battery):
    mock_restore_cache(hass, [State(PAUSE_SWITCH_ID, STATE_OFF)])

    _entry, handle = await setup_battery()

    assert handle._switches[PAUSE_BATTERY] is False
    assert hass.states.get(PAUSE_SWITCH_ID).state == STATE_OFF


async def test_unavailable_restored_switch_stays_off(hass, setup_battery):
    mock_restore_cache(hass, [State(PAUSE_SWITCH_ID, STATE_UNAVAILABLE)])

    _entry, handle = await setup_battery()

    assert handle._switches[PAUSE_BATTERY] is False
    assert hass.states.get(PAUSE_SWITCH_ID).state == STATE_OFF
