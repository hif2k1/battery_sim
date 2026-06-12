"""Tests for the battery_sim switch platform."""
from homeassistant.const import STATE_OFF, STATE_ON

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
