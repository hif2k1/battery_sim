"""Constants for the utility meter component."""
DOMAIN = "battery_sim"

QUARTER_HOURLY = "quarter-hourly"
HOURLY = "hourly"
DAILY = "daily"
WEEKLY = "weekly"
MONTHLY = "monthly"
BIMONTHLY = "bimonthly"
QUARTERLY = "quarterly"
YEARLY = "yearly"

#BATTERY_TYPES = []

DATA_UTILITY = "battery_sim_data"

CONF_BATTERY = "battery"
CONF_IMPORT_SENSOR = "import_sensor"
CONF_EXPORT_SENSOR = "export_sensor"
CONF_BATTERY_SIZE = "size_kwh"
CONF_BATTERY_MAX_DISCHARGE_RATE = "max_discharge_rate_kw"
CONF_BATTERY_MAX_CHARGE_RATE = "max_charge_rate_kw"
CONF_BATTERY_EFFICIENCY = "efficiency"
ATTR_VALUE = "value"

ATTR_SOURCE_ID = "source"
ATTR_STATUS = "status"
PRECISION = 3
ATTR_ENERGY_SAVED = "energy_saved"
CHARGING = "charging"
DISCHARGING = "discharging"
ATTR_CHARGE_PERCENTAGE = "percentage"