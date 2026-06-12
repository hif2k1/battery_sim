"""Tests for the battery_sim sensor platform."""
import pytest

from homeassistant.core import State
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.battery_sim.const import (
    ATTR_CHARGE_PERCENTAGE,
    ATTR_ENERGY_SAVED,
    ATTR_MONEY_SAVED,
    ATTR_STATUS,
    ATTR_STORED_ENERGY_VALUE,
    CONF_BATTERY_SIZE,
    GRID_IMPORT_SIM,
    MESSAGE_TYPE_BATTERY_UPDATE,
    MODE_IDLE,
    PERCENTAGE_ENERGY_IMPORT_SAVED,
)

from pytest_homeassistant_custom_component.common import mock_restore_cache

from .common import (
    AVERAGE_VALUE_SENSOR_ID,
    BATTERY_ENTITY_ID,
    BATTERY_MODE_SENSOR_ID,
    BATTERY_NAME,
    CHARGE_EFFICIENCY_SENSOR_ID,
    CHARGING_RATE_SENSOR_ID,
    CYCLES_SENSOR_ID,
    DEGRADATION_SENSOR_ID,
    DISCHARGE_EFFICIENCY_SENSOR_ID,
    DISCHARGING_RATE_SENSOR_ID,
    ENERGY_IN_SENSOR_ID,
    ENERGY_OUT_SENSOR_ID,
    ENERGY_SAVED_SENSOR_ID,
    IMPORT_SENSOR_ID,
    KWH_ATTRIBUTES,
    MONEY_SAVED_EXPORT_SENSOR_ID,
    MONEY_SAVED_IMPORT_SENSOR_ID,
    MONEY_SAVED_SENSOR_ID,
    SIM_EXPORT_SENSOR_ID,
    SIM_IMPORT_SENSOR_ID,
    SOLAR_CAP_SENSOR_ID,
    config_with_solar,
)


def battery_update_signal():
    return f"{BATTERY_NAME}-{MESSAGE_TYPE_BATTERY_UPDATE}"


async def test_all_sensors_created_with_initial_values(hass, setup_battery):
    await setup_battery()

    expected_initial_states = {
        BATTERY_ENTITY_ID: "5.0",
        BATTERY_MODE_SENSOR_ID: MODE_IDLE,
        ENERGY_SAVED_SENSOR_ID: "0.0",
        ENERGY_IN_SENSOR_ID: "0.0",
        ENERGY_OUT_SENSOR_ID: "0.0",
        CHARGING_RATE_SENSOR_ID: "0.0",
        DISCHARGING_RATE_SENSOR_ID: "0.0",
        CHARGE_EFFICIENCY_SENSOR_ID: "0.8",
        DISCHARGE_EFFICIENCY_SENSOR_ID: "0.9",
        SIM_IMPORT_SENSOR_ID: "0.0",
        SIM_EXPORT_SENSOR_ID: "0.0",
        CYCLES_SENSOR_ID: "0.0",
        DEGRADATION_SENSOR_ID: "1.0",
        MONEY_SAVED_IMPORT_SENSOR_ID: "0.0",
        MONEY_SAVED_SENSOR_ID: "0.0",
        MONEY_SAVED_EXPORT_SENSOR_ID: "0.0",
        AVERAGE_VALUE_SENSOR_ID: "0.0",
    }
    for entity_id, expected_state in expected_initial_states.items():
        state = hass.states.get(entity_id)
        assert state is not None, f"missing entity {entity_id}"
        assert state.state == expected_state, f"unexpected state for {entity_id}"

    # No solar sensor configured, so no solar power cap entity.
    assert hass.states.get(SOLAR_CAP_SENSOR_ID) is None


async def test_solar_power_cap_sensor_created_with_solar_config(
    hass, setup_battery
):
    await setup_battery(config_with_solar())
    assert hass.states.get(SOLAR_CAP_SENSOR_ID) is not None


async def test_battery_sensor_attributes(hass, setup_battery):
    await setup_battery()
    state = hass.states.get(BATTERY_ENTITY_ID)

    assert state.attributes[ATTR_STATUS] == MODE_IDLE
    assert state.attributes[ATTR_CHARGE_PERCENTAGE] == 50
    assert state.attributes[CONF_BATTERY_SIZE] == 10.0
    assert IMPORT_SENSOR_ID in state.attributes["sources"]


async def test_mode_sensor_attributes(hass, setup_battery):
    await setup_battery()
    state = hass.states.get(BATTERY_MODE_SENSOR_ID)

    assert state.attributes[ATTR_STATUS] == "Normal"
    assert state.attributes[ATTR_CHARGE_PERCENTAGE] == 50


async def test_sensors_update_when_battery_updates(hass, setup_battery):
    _entry, handle = await setup_battery()

    handle._sensors[ATTR_ENERGY_SAVED] = 12.3456
    handle._sensors[ATTR_MONEY_SAVED] = 1.23456
    handle.async_set_battery_charge_state(7.5)
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == "7.5"
    assert (
        hass.states.get(BATTERY_ENTITY_ID).attributes[ATTR_CHARGE_PERCENTAGE] == 50
    )
    # Energy values round to 3 decimals, money to 2.
    assert hass.states.get(ENERGY_SAVED_SENSOR_ID).state == "12.346"
    assert hass.states.get(MONEY_SAVED_SENSOR_ID).state == "1.23"


async def test_percentage_energy_saved_attribute(hass, setup_battery):
    hass.states.async_set(IMPORT_SENSOR_ID, "10.0", KWH_ATTRIBUTES)
    _entry, handle = await setup_battery()

    handle._sensors[GRID_IMPORT_SIM] = 8.0
    async_dispatcher_send(hass, battery_update_signal())
    await hass.async_block_till_done()

    state = hass.states.get(SIM_IMPORT_SENSOR_ID)
    assert state.state == "8.0"
    assert state.attributes[PERCENTAGE_ENERGY_IMPORT_SAVED] == 20.0


async def test_percentage_energy_saved_attribute_zero_import(
    hass, setup_battery, caplog
):
    hass.states.async_set(IMPORT_SENSOR_ID, "0.0", KWH_ATTRIBUTES)
    _entry, handle = await setup_battery()

    handle._sensors[GRID_IMPORT_SIM] = 8.0
    async_dispatcher_send(hass, battery_update_signal())
    await hass.async_block_till_done()

    state = hass.states.get(SIM_IMPORT_SENSOR_ID)
    assert state.attributes[PERCENTAGE_ENERGY_IMPORT_SAVED] == 0
    assert "Division by zero" in caplog.text


async def test_restore_battery_charge_state(hass, setup_battery):
    mock_restore_cache(hass, [State(BATTERY_ENTITY_ID, "7.5")])
    _entry, handle = await setup_battery()

    assert handle._charge_state == pytest.approx(7.5)
    assert hass.states.get(BATTERY_ENTITY_ID).state == "7.5"


async def test_restore_battery_charge_clipped_to_capacity(hass, setup_battery):
    mock_restore_cache(hass, [State(BATTERY_ENTITY_ID, "25.0")])
    _entry, handle = await setup_battery()

    assert handle._charge_state == pytest.approx(10.0)


async def test_restore_display_sensor_value(hass, setup_battery):
    mock_restore_cache(hass, [State(ENERGY_SAVED_SENSOR_ID, "12.345")])
    _entry, handle = await setup_battery()

    assert handle._sensors[ATTR_ENERGY_SAVED] == pytest.approx(12.345)
    assert hass.states.get(ENERGY_SAVED_SENSOR_ID).state == "12.345"


async def test_restore_invalid_states_ignored(hass, setup_battery):
    mock_restore_cache(
        hass,
        [
            State(BATTERY_ENTITY_ID, "unknown"),
            State(ENERGY_SAVED_SENSOR_ID, "unavailable"),
        ],
    )
    _entry, handle = await setup_battery()

    assert handle._charge_state == pytest.approx(5.0)
    assert handle._sensors[ATTR_ENERGY_SAVED] == 0.0


async def test_restore_non_numeric_state_ignored(hass, setup_battery):
    mock_restore_cache(hass, [State(ENERGY_SAVED_SENSOR_ID, "garbage")])
    _entry, handle = await setup_battery()

    assert handle._sensors[ATTR_ENERGY_SAVED] == 0.0


async def test_restore_average_energy_value_with_stored_value_attribute(
    hass, setup_battery
):
    mock_restore_cache(
        hass,
        [
            State(BATTERY_ENTITY_ID, "5.0"),
            State(
                AVERAGE_VALUE_SENSOR_ID,
                "0.25",
                {ATTR_STORED_ENERGY_VALUE: 1.25},
            ),
        ],
    )
    _entry, handle = await setup_battery()

    assert handle._stored_energy_value == pytest.approx(1.25)
    state = hass.states.get(AVERAGE_VALUE_SENSOR_ID)
    assert state.state == "0.25"
    assert state.attributes[ATTR_STORED_ENERGY_VALUE] == pytest.approx(1.25)


async def test_restore_legacy_average_energy_value_without_attribute(
    hass, setup_battery
):
    """Old recorder states only stored the average; the total is rebuilt."""
    mock_restore_cache(
        hass,
        [
            State(BATTERY_ENTITY_ID, "4.0"),
            State(AVERAGE_VALUE_SENSOR_ID, "0.2"),
        ],
    )
    _entry, handle = await setup_battery()

    assert handle._charge_state == pytest.approx(4.0)
    assert handle._stored_energy_value == pytest.approx(0.2 * 4.0)
    assert hass.states.get(AVERAGE_VALUE_SENSOR_ID).state == "0.2"
