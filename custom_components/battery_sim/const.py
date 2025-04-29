"""Constants for the battery_sim component."""

DOMAIN = "battery_sim"

BATTERY_TYPE = "battery"

BATTERY_PLATFORMS = ["sensor", "switch", "button", "select", "number"]

MESSAGE_TYPE_GENERAL = "BatteryResetMessage"
MESSAGE_TYPE_BATTERY_RESET_IMP = "BatteryResetImportSim"
MESSAGE_TYPE_BATTERY_RESET_EXP = "BatteryResetExportSim"
MESSAGE_TYPE_BATTERY_UPDATE = "BatteryUpdateMessage"

DATA_UTILITY = "battery_sim_data"

SETUP_TYPE = "setup_type"
CONFIG_FLOW = "config_flow"
YAML = "yaml"

CONF_BATTERY = "battery"
CONF_INPUT_LIST = "input_list"
CONF_IMPORT_SENSOR = "import_sensor"
CONF_SECOND_IMPORT_SENSOR = "second_import_sensor"
CONF_EXPORT_SENSOR = "export_sensor"
CONF_SECOND_EXPORT_SENSOR = "second_export_sensor"
CONF_BATTERY_SIZE = "size_kwh"
CONF_BATTERY_MAX_DISCHARGE_RATE = "max_discharge_rate_kw"
CONF_BATTERY_MAX_CHARGE_RATE = "max_charge_rate_kw"
CONF_BATTERY_EFFICIENCY = "efficiency"
CONF_ENERGY_TARIFF = "energy_tariff"
CONF_ENERGY_IMPORT_TARIFF = "energy_import_tariff"
CONF_ENERGY_EXPORT_TARIFF = "energy_export_tariff"
CONF_UNIQUE_NAME = "unique_name"
CONF_UPDATE_FREQUENCY = "update_frequency"
ATTR_VALUE = "value"
METER_TYPE = "type_of_energy_meter"
ONE_IMPORT_ONE_EXPORT_METER = "one_import_one_export"
TWO_IMPORT_ONE_EXPORT_METER = "two_import_one_export"
TWO_IMPORT_TWO_EXPORT_METER = "two_import_two_export"
TARIFF_TYPE = "tariff_type"
NO_TARIFF_INFO = "No tariff information"
TARIFF_SENSOR = "tariff_sensor"
FIXED_TARIFF = "fixed_tariff"
TARIFF_SENSOR_ENTITIES = "Sensors that track tariffs"
FIXED_NUMERICAL_TARIFFS = "Fixed value for tariffs"
NEXT_STEP = "next_step"
ADD_ANOTHER = "Add another"
ALL_DONE = "All done"

ATTR_SOURCE_ID = "sources"
ATTR_STATUS = "status"
PRECISION = 3
ATTR_ENERGY_SAVED = "total energy saved"
ATTR_ENERGY_SAVED_TODAY = "energy_saved_today"
ATTR_ENERGY_SAVED_WEEK = "energy_saved_this_week"
ATTR_ENERGY_SAVED_MONTH = "energy_saved_this_month"
ATTR_DATE_RECORDING_STARTED = "date_recording_started"
ATTR_ENERGY_BATTERY_OUT = "battery_energy_out"
ATTR_ENERGY_BATTERY_IN = "battery_energy_in"
ATTR_MONEY_SAVED = "total_money_saved"
ATTR_MONEY_SAVED_IMPORT = "money_saved_on_imports"
ATTR_MONEY_SAVED_EXPORT = "extra_money_earned_on_exports"
CHARGING_RATE = "current charging rate"
DISCHARGING_RATE = "current discharging rate"
ATTR_CHARGE_PERCENTAGE = "percentage"
GRID_EXPORT_SIM = "simulated grid export after battery charging"
GRID_IMPORT_SIM = "simulated grid import after battery discharging"
GRID_SECOND_EXPORT_SIM = "simulated second grid export after battery charging"
GRID_SECOND_IMPORT_SIM = "simulated second grid import after battery discharging"
ICON_CHARGING = "mdi:battery-charging-50"
ICON_DISCHARGING = "mdi:battery-50"
ICON_FULL = "mdi:battery"
ICON_EMPTY = "mdi:battery-outline"
CHARGE_LIMIT = "charge_limit"
DISCHARGE_LIMIT = "discharge_limit"
MINIMUM_SOC = "minimum_soc"
MAXIMUM_SOC = "maximum_soc"
OVERIDE_CHARGING = "force_charge"
FORCE_DISCHARGE = "force_discharge"
CHARGE_ONLY = "charge_only"
DISCHARGE_ONLY = "discharge_only"
PAUSE_BATTERY = "pause_battery"
RESET_BATTERY = "reset_battery"
DEFAULT_MODE = "default_mode"
PERCENTAGE_ENERGY_IMPORT_SAVED = "percentage_import_energy_saved"
BATTERY_CYCLES = "battery_cycles"
SENSOR_ID = "sensor_id"
SENSOR_TYPE = "sensor_type"
TARIFF = "tariff_sensor_or_value"
CONF_SECOND_ENERGY_IMPORT_TARIFF = "second_energy_import_tariff"
CONF_SECOND_ENERGY_EXPORT_TARIFF = "second_energy_export_tariff"
IMPORT = "Import"
EXPORT = "Export"
SIMULATED_SENSOR = "simulated_sensor"

BATTERY_MODE = "Battery_mode_now"
MODE_IDLE = "Idle/Paused"
MODE_CHARGING = "Charging"
MODE_DISCHARGING = "Discharging"
MODE_FORCE_CHARGING = "Forced charging"
MODE_FORCE_DISCHARGING = "Forced discharging"
MODE_FULL = "Full"
MODE_EMPTY = "Empty"

BATTERY_OPTIONS = {
    "Tesla Powerwall": {
        CONF_BATTERY_SIZE: 13.5,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5.0,
        CONF_BATTERY_MAX_CHARGE_RATE: 3.68,
        CONF_BATTERY_EFFICIENCY: 0.9,
    },
    "LG Chem": {
        CONF_BATTERY_SIZE: 9.3,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5.0,
        CONF_BATTERY_MAX_CHARGE_RATE: 3.3,
        CONF_BATTERY_EFFICIENCY: 0.95,
    },
    "Sonnen Eco": {
        CONF_BATTERY_SIZE: 5.0,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 2.5,
        CONF_BATTERY_MAX_CHARGE_RATE: 2.5,
        CONF_BATTERY_EFFICIENCY: 0.9,
    },
    "Pika Harbour": {
        CONF_BATTERY_SIZE: 8.6,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 4.2,
        CONF_BATTERY_MAX_CHARGE_RATE: 4.2,
        CONF_BATTERY_EFFICIENCY: 0.965,
    },
    "Enphase 3T (2nd Gen)": {
        CONF_BATTERY_SIZE: 3.36,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 1.92,
        CONF_BATTERY_MAX_CHARGE_RATE: 1.28,
        CONF_BATTERY_EFFICIENCY: 0.965,
    },
    "Enphase 10T (2nd Gen)": {
        CONF_BATTERY_SIZE: 10.08,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5.0,
        CONF_BATTERY_MAX_CHARGE_RATE: 3.84,
        CONF_BATTERY_EFFICIENCY: 0.89,
    },
    "Enphase 5P (3rd Gen)": {
        CONF_BATTERY_SIZE: 5.0,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5.7,
        CONF_BATTERY_MAX_CHARGE_RATE: 3.84,
        CONF_BATTERY_EFFICIENCY: 0.90,
    },
    "Sessy": {
        CONF_BATTERY_SIZE: 5.0,
        CONF_BATTERY_EFFICIENCY: 0.81,
        CONF_BATTERY_MAX_CHARGE_RATE: 2.2,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 1.7,
    },
    "Huawei Luna2000 5kW": {
        CONF_BATTERY_SIZE: 5.0,
        CONF_BATTERY_EFFICIENCY: 0.99,
        CONF_BATTERY_MAX_CHARGE_RATE: 2.5,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 2.5,
    },
    "Huawei Luna2000 10kW": {
        CONF_BATTERY_SIZE: 10.0,
        CONF_BATTERY_EFFICIENCY: 0.99,
        CONF_BATTERY_MAX_CHARGE_RATE: 5,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5,
    },
    "Huawei Luna2000 15kW": {
        CONF_BATTERY_SIZE: 15.0,
        CONF_BATTERY_EFFICIENCY: 0.99,
        CONF_BATTERY_MAX_CHARGE_RATE: 5,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5,
    },
    "Solax 5.8kWh Master": {
        CONF_BATTERY_SIZE: 5.1,
        CONF_BATTERY_EFFICIENCY: 0.95,
        CONF_BATTERY_MAX_CHARGE_RATE: 4,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 4,
    },
    "BYD Battery Box HVS 5.1kWh": {
        CONF_BATTERY_SIZE: 5.1,
        CONF_BATTERY_EFFICIENCY: 0.96,
        CONF_BATTERY_MAX_CHARGE_RATE: 5.7,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5.7,
    },
    "BYD Battery Box HVS 7.7kWh": {
        CONF_BATTERY_SIZE: 7.68,
        CONF_BATTERY_EFFICIENCY: 0.96,
        CONF_BATTERY_MAX_CHARGE_RATE: 5.7,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5.7,
    },
    "BYD Battery Box HVS 10.2kWh": {
        CONF_BATTERY_SIZE: 10.2,
        CONF_BATTERY_EFFICIENCY: 0.96,
        CONF_BATTERY_MAX_CHARGE_RATE: 5.7,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5.7,
    },
    "BYD Battery Box HVS 12.8kWh": {
        CONF_BATTERY_SIZE: 12.8,
        CONF_BATTERY_EFFICIENCY: 0.96,
        CONF_BATTERY_MAX_CHARGE_RATE: 5.7,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5.7,
    },
    "BYD Battery Box HVM 8.3kWh": {
        CONF_BATTERY_SIZE: 8.28,
        CONF_BATTERY_EFFICIENCY: 0.96,
        CONF_BATTERY_MAX_CHARGE_RATE: 7,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 7,
    },
    "BYD Battery Box HVM 11.0kWh": {
        CONF_BATTERY_SIZE: 11.04,
        CONF_BATTERY_EFFICIENCY: 0.96,
        CONF_BATTERY_MAX_CHARGE_RATE: 10.2,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 10.2,
    },
    "BYD Battery Box HVM 13.8kWh": {
        CONF_BATTERY_SIZE: 13.8,
        CONF_BATTERY_EFFICIENCY: 0.96,
        CONF_BATTERY_MAX_CHARGE_RATE: 11.5,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 11.5,
    },
    "BYD Battery Box HVM 16.6kWh": {
        CONF_BATTERY_SIZE: 16.56,
        CONF_BATTERY_EFFICIENCY: 0.96,
        CONF_BATTERY_MAX_CHARGE_RATE: 11.5,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 11.5,
    },
    "BYD Battery Box HVM 19.3kWh": {
        CONF_BATTERY_SIZE: 19.32,
        CONF_BATTERY_EFFICIENCY: 0.96,
        CONF_BATTERY_MAX_CHARGE_RATE: 11.5,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 11.5,
    },
    "BYD Battery Box HVM 22.1kWh": {
        CONF_BATTERY_SIZE: 22.08,
        CONF_BATTERY_EFFICIENCY: 0.96,
        CONF_BATTERY_MAX_CHARGE_RATE: 11.5,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 11.5,
    },
    "HomeWizard Energy Plug-in Battery 2.7kWh": {
        CONF_BATTERY_SIZE: 2.473,
        CONF_BATTERY_EFFICIENCY: 0.95,
        CONF_BATTERY_MAX_CHARGE_RATE: 0.8,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 0.8,
    },
    "Custom": {},
}
