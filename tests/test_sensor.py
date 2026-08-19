"""Tests for the battery_sim sensor platform."""
import pytest

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfEnergy,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.core import State
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.battery_sim.const import (
    ATTR_ENERGY_SAVED,
    ATTR_MONEY_SAVED,
    ATTR_STATUS,
    ATTR_STORED_ENERGY_VALUE,
    CONF_BATTERY_SIZE,
    GRID_EXPORT_SIM,
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
    BATTERY_SOC_SENSOR_ID,
    CHARGE_EFFICIENCY_SENSOR_ID,
    CHARGING_RATE_SENSOR_ID,
    CYCLES_SENSOR_ID,
    DEGRADATION_SENSOR_ID,
    DISCHARGE_EFFICIENCY_SENSOR_ID,
    DISCHARGING_RATE_SENSOR_ID,
    ENERGY_IN_SENSOR_ID,
    ENERGY_OUT_SENSOR_ID,
    ENERGY_SAVED_SENSOR_ID,
    EXPORT_SENSOR_ID,
    IMPORT_SENSOR_ID,
    KWH_ATTRIBUTES,
    MONEY_SAVED_EXPORT_SENSOR_ID,
    MONEY_SAVED_IMPORT_SENSOR_ID,
    MONEY_SAVED_SENSOR_ID,
    SIM_EXPORT_SENSOR_ID,
    SIM_IMPORT_SENSOR_ID,
    SOLAR_CAP_SENSOR_ID,
    WH_ATTRIBUTES,
    config_with_solar,
)

# The percentage used to be published as an attribute under this key. It is now
# a standalone sensor, so the key must no longer appear on any battery entity.
ATTR_CHARGE_PERCENTAGE_LEGACY = "percentage"


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
        BATTERY_SOC_SENSOR_ID: "50",
    }
    for entity_id, expected_state in expected_initial_states.items():
        state = hass.states.get(entity_id)
        assert state is not None, f"missing entity {entity_id}"
        assert state.state == expected_state, f"unexpected state for {entity_id}"

    # No solar sensor configured, so no solar power cap entity.
    assert hass.states.get(SOLAR_CAP_SENSOR_ID) is None


async def test_display_sensor_unit_can_be_overridden_by_the_user(
    hass, setup_battery
):
    """The unit must be published as the native one so HA can convert it.

    Home Assistant converts a sensor's value from its native unit to the unit
    the user picked in the entity settings. A sensor that only overrides
    `unit_of_measurement` bypasses that conversion entirely.
    """
    await setup_battery()
    entity_registry = er.async_get(hass)

    assert (
        hass.states.get(ENERGY_SAVED_SENSOR_ID).attributes[ATTR_UNIT_OF_MEASUREMENT]
        == UnitOfEnergy.KILO_WATT_HOUR
    )

    entity_registry.async_update_entity_options(
        ENERGY_SAVED_SENSOR_ID,
        "sensor",
        {"unit_of_measurement": UnitOfEnergy.WATT_HOUR},
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENERGY_SAVED_SENSOR_ID)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.WATT_HOUR


async def test_solar_power_cap_sensor_created_with_solar_config(
    hass, setup_battery
):
    await setup_battery(config_with_solar())
    assert hass.states.get(SOLAR_CAP_SENSOR_ID) is not None


async def test_battery_sensor_attributes(hass, setup_battery):
    await setup_battery()
    state = hass.states.get(BATTERY_ENTITY_ID)

    assert state.attributes[ATTR_STATUS] == MODE_IDLE
    assert ATTR_CHARGE_PERCENTAGE_LEGACY not in state.attributes
    assert state.attributes[CONF_BATTERY_SIZE] == 10.0
    assert IMPORT_SENSOR_ID in state.attributes["sources"]


async def test_state_of_charge_sensor_is_a_battery_percentage(hass, setup_battery):
    """The state of charge is a first class entity with a class and a unit."""
    await setup_battery()
    state = hass.states.get(BATTERY_SOC_SENSOR_ID)

    assert state.state == "50"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.BATTERY
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


async def test_state_of_charge_sensor_follows_the_charge_state(hass, setup_battery):
    """The state of charge is derived, so it also tracks direct charge changes."""
    _entry, handle = await setup_battery()

    handle.async_set_battery_charge_state(2.5)
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_SOC_SENSOR_ID).state == "25"


async def test_state_of_charge_sensor_follows_restored_charge_state(
    hass, setup_battery
):
    """The state of charge must be right at startup, before the first update."""
    mock_restore_cache(hass, [State(BATTERY_ENTITY_ID, "8.0")])
    await setup_battery()

    assert hass.states.get(BATTERY_SOC_SENSOR_ID).state == "80"


async def test_state_of_charge_sensor_accounts_for_degradation(hass, setup_battery):
    """The percentage is relative to the remaining, degraded capacity."""
    _entry, handle = await setup_battery()

    # Half of the rated cycles degrades a 10 kWh battery to 9 kWh here.
    handle.async_set_battery_cycles(3000.0)
    handle.async_set_battery_charge_state(4.5)
    await hass.async_block_till_done()

    assert handle.current_max_capacity == pytest.approx(9.0)
    assert hass.states.get(BATTERY_SOC_SENSOR_ID).state == "50"


async def test_mode_sensor_attributes(hass, setup_battery):
    await setup_battery()
    state = hass.states.get(BATTERY_MODE_SENSOR_ID)

    assert state.attributes[ATTR_STATUS] == "Normal"
    assert ATTR_CHARGE_PERCENTAGE_LEGACY not in state.attributes


async def test_sensors_update_when_battery_updates(hass, setup_battery):
    _entry, handle = await setup_battery()

    handle._sensors[ATTR_ENERGY_SAVED] = 12.3456
    handle._sensors[ATTR_MONEY_SAVED] = 1.23456
    handle.async_set_battery_charge_state(7.5)
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == "7.5"
    assert hass.states.get(BATTERY_SOC_SENSOR_ID).state == "75"
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


async def test_new_battery_sim_sensors_sync_to_sources(hass, setup_battery):
    """A newly created battery starts its simulated meters at the source values."""
    hass.states.async_set(IMPORT_SENSOR_ID, "123.4", KWH_ATTRIBUTES)
    hass.states.async_set(EXPORT_SENSOR_ID, "55.5", KWH_ATTRIBUTES)
    _entry, handle = await setup_battery()

    assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(123.4)
    assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(55.5)
    assert hass.states.get(SIM_IMPORT_SENSOR_ID).state == "123.4"
    assert hass.states.get(SIM_EXPORT_SENSOR_ID).state == "55.5"


async def test_new_battery_sim_sensors_zero_when_sources_not_ready(
    hass, setup_battery
):
    hass.states.async_set(IMPORT_SENSOR_ID, "unavailable", KWH_ATTRIBUTES)
    _entry, handle = await setup_battery()

    assert handle._sensors[GRID_IMPORT_SIM] == 0.0
    assert handle._sensors[GRID_EXPORT_SIM] == 0.0


async def test_new_battery_sim_sensor_converts_wh_source(hass, setup_battery):
    """Source meters reporting in Wh are converted to kWh when syncing."""
    hass.states.async_set(IMPORT_SENSOR_ID, "123400", WH_ATTRIBUTES)
    hass.states.async_set(EXPORT_SENSOR_ID, "55500", WH_ATTRIBUTES)
    _entry, handle = await setup_battery()

    assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(123.4)
    assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(55.5)


async def test_new_battery_sim_sensor_ignores_unsupported_units(
    hass, setup_battery, caplog
):
    hass.states.async_set(
        IMPORT_SENSOR_ID, "123.4", {ATTR_UNIT_OF_MEASUREMENT: "MJ"}
    )
    _entry, handle = await setup_battery()

    assert handle._sensors[GRID_IMPORT_SIM] == 0.0
    assert "unsupported energy unit" in caplog.text


async def test_restored_sim_sensor_not_overwritten_by_source(hass, setup_battery):
    hass.states.async_set(IMPORT_SENSOR_ID, "123.4", KWH_ATTRIBUTES)
    mock_restore_cache(hass, [State(SIM_IMPORT_SENSOR_ID, "100.0")])
    _entry, handle = await setup_battery()

    assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(100.0)
    assert hass.states.get(SIM_IMPORT_SENSOR_ID).state == "100.0"


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
