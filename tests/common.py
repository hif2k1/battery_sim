"""Shared constants and helpers for battery_sim tests."""
from copy import deepcopy

import homeassistant.util.dt as dt_util
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, CONF_NAME, UnitOfEnergy

from custom_components.battery_sim.const import (
    CONF_BATTERY_CHARGE_EFFICIENCY,
    CONF_BATTERY_DISCHARGE_EFFICIENCY,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_SIZE,
    CONF_END_OF_LIFE_DEGRADATION,
    CONF_INPUT_LIST,
    CONF_MINIMUM_USER_SELECTABLE_SOC,
    CONF_NOMINAL_INVERTER_POWER,
    CONF_RATED_BATTERY_CYCLES,
    CONF_SOLAR_ENERGY_SENSOR,
    CONF_UPDATE_FREQUENCY,
    CONFIG_FLOW,
    EXPORT,
    FIXED_TARIFF,
    GRID_EXPORT_SIM,
    GRID_IMPORT_SIM,
    IMPORT,
    NO_TARIFF_INFO,
    SENSOR_ID,
    SENSOR_TYPE,
    SETUP_TYPE,
    SIMULATED_SENSOR,
    TARIFF_SENSOR,
    TARIFF_TYPE,
)

BATTERY_NAME = "test_battery"
IMPORT_SENSOR_ID = "sensor.test_import_energy"
EXPORT_SENSOR_ID = "sensor.test_export_energy"
SOLAR_SENSOR_ID = "sensor.test_solar_energy"
IMPORT_TARIFF_SENSOR_ID = "sensor.test_import_tariff"
EXPORT_TARIFF_SENSOR_ID = "sensor.test_export_tariff"

IMPORT_TARIFF = 0.30
EXPORT_TARIFF = 0.10

BATTERY_ENTITY_ID = "sensor.test_battery"
BATTERY_MODE_SENSOR_ID = "sensor.test_battery_battery_mode_now"
ENERGY_SAVED_SENSOR_ID = "sensor.test_battery_total_energy_saved"
ENERGY_IN_SENSOR_ID = "sensor.test_battery_battery_energy_in"
ENERGY_OUT_SENSOR_ID = "sensor.test_battery_battery_energy_out"
CHARGING_RATE_SENSOR_ID = "sensor.test_battery_current_charging_rate"
DISCHARGING_RATE_SENSOR_ID = "sensor.test_battery_current_discharging_rate"
CHARGE_EFFICIENCY_SENSOR_ID = "sensor.test_battery_last_charge_efficiency"
DISCHARGE_EFFICIENCY_SENSOR_ID = "sensor.test_battery_last_discharge_efficiency"
SIM_IMPORT_SENSOR_ID = (
    "sensor.test_battery_simulated_grid_import_after_battery_discharging"
)
SIM_EXPORT_SENSOR_ID = (
    "sensor.test_battery_simulated_grid_export_after_battery_charging"
)
CYCLES_SENSOR_ID = "sensor.test_battery_battery_cycles"
DEGRADATION_SENSOR_ID = "sensor.test_battery_battery_degradation"
MONEY_SAVED_IMPORT_SENSOR_ID = "sensor.test_battery_money_saved_on_imports"
MONEY_SAVED_SENSOR_ID = "sensor.test_battery_total_money_saved"
MONEY_SAVED_EXPORT_SENSOR_ID = "sensor.test_battery_extra_money_earned_on_exports"
AVERAGE_VALUE_SENSOR_ID = "sensor.test_battery_average_energy_value"
SOLAR_CAP_SENSOR_ID = "sensor.test_battery_solar_power_cap"
PAUSE_SWITCH_ID = "switch.test_battery_pause_battery"
RESET_BUTTON_ID = "button.test_battery_reset_battery"
MODE_SELECT_ID = "select.test_battery_battery_mode"
CHARGE_LIMIT_NUMBER_ID = "number.test_battery_charge_limit"
DISCHARGE_LIMIT_NUMBER_ID = "number.test_battery_discharge_limit"
MINIMUM_SOC_NUMBER_ID = "number.test_battery_minimum_soc"
MAXIMUM_SOC_NUMBER_ID = "number.test_battery_maximum_soc"

KWH_ATTRIBUTES = {
    ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
    "device_class": "energy",
    "state_class": "total_increasing",
}
WH_ATTRIBUTES = {
    ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.WATT_HOUR,
    "device_class": "energy",
    "state_class": "total_increasing",
}

BASE_CONFIG = {
    SETUP_TYPE: CONFIG_FLOW,
    CONF_NAME: BATTERY_NAME,
    CONF_BATTERY_SIZE: 10.0,
    CONF_BATTERY_MAX_DISCHARGE_RATE: 5.0,
    CONF_BATTERY_MAX_CHARGE_RATE: 4.0,
    CONF_BATTERY_DISCHARGE_EFFICIENCY: 0.9,
    CONF_BATTERY_CHARGE_EFFICIENCY: 0.8,
    CONF_RATED_BATTERY_CYCLES: 6000.0,
    CONF_END_OF_LIFE_DEGRADATION: 0.8,
    CONF_UPDATE_FREQUENCY: 60,
    CONF_MINIMUM_USER_SELECTABLE_SOC: 0.0,
    CONF_INPUT_LIST: [
        {
            SENSOR_ID: IMPORT_SENSOR_ID,
            SENSOR_TYPE: IMPORT,
            SIMULATED_SENSOR: GRID_IMPORT_SIM,
            TARIFF_TYPE: NO_TARIFF_INFO,
        },
        {
            SENSOR_ID: EXPORT_SENSOR_ID,
            SENSOR_TYPE: EXPORT,
            SIMULATED_SENSOR: GRID_EXPORT_SIM,
            TARIFF_TYPE: NO_TARIFF_INFO,
        },
    ],
}


def base_config(**overrides):
    """Return a copy of the standard test battery configuration."""
    config = deepcopy(BASE_CONFIG)
    config.update(overrides)
    return config


def config_with_fixed_tariffs(**overrides):
    """Return a config whose import/export inputs carry fixed tariffs."""
    config = base_config(**overrides)
    config[CONF_INPUT_LIST][0][TARIFF_TYPE] = FIXED_TARIFF
    config[CONF_INPUT_LIST][0][FIXED_TARIFF] = IMPORT_TARIFF
    config[CONF_INPUT_LIST][1][TARIFF_TYPE] = FIXED_TARIFF
    config[CONF_INPUT_LIST][1][FIXED_TARIFF] = EXPORT_TARIFF
    return config


def config_with_tariff_sensors(**overrides):
    """Return a config whose import/export inputs use tariff sensor entities."""
    config = base_config(**overrides)
    config[CONF_INPUT_LIST][0][TARIFF_TYPE] = TARIFF_SENSOR
    config[CONF_INPUT_LIST][0][TARIFF_SENSOR] = IMPORT_TARIFF_SENSOR_ID
    config[CONF_INPUT_LIST][1][TARIFF_TYPE] = TARIFF_SENSOR
    config[CONF_INPUT_LIST][1][TARIFF_SENSOR] = EXPORT_TARIFF_SENSOR_ID
    return config


def config_with_solar(nominal_inverter_power=None, **overrides):
    """Return a config with a solar production sensor configured."""
    config = base_config(**overrides)
    config[CONF_SOLAR_ENERGY_SENSOR] = SOLAR_SENSOR_ID
    if nominal_inverter_power is not None:
        config[CONF_NOMINAL_INVERTER_POWER] = nominal_inverter_power
    return config


def rewind_last_update(handle, seconds):
    """Pretend the last battery update happened `seconds` ago."""
    handle._last_battery_update_time = dt_util.utcnow().timestamp() - seconds


def link_meter_readings(handle):
    """Mark the import/export inputs as the most recently read meters."""
    handle._last_import_reading_sensor_data = handle._inputs[0]
    handle._last_export_reading_sensor_data = handle._inputs[1]
