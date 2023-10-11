"""Simulates a battery to evaluate how much energy it could save."""
import logging
import time

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.dispatcher import (
    dispatcher_send,
    async_dispatcher_connect
)

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)

from .const import (
    ATTR_ENERGY_BATTERY_IN,
    ATTR_ENERGY_BATTERY_OUT,
    ATTR_ENERGY_SAVED,
    ATTR_MONEY_SAVED_EXPORT,
    ATTR_MONEY_SAVED_IMPORT,
    ATTR_MONEY_SAVED,
    BATTERY_CYCLES,
    BATTERY_MODE,
    BATTERY_PLATFORMS,
    CHARGE_ONLY,
    CHARGING_RATE,
    CONF_BATTERY_EFFICIENCY,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_SIZE,
    CONF_BATTERY,
    CONF_ENERGY_EXPORT_TARIFF,
    CONF_ENERGY_IMPORT_TARIFF,
    CONF_ENERGY_TARIFF,
    CONF_EXPORT_SENSOR,
    CONF_IMPORT_SENSOR,
    CONF_SECOND_EXPORT_SENSOR,
    CONF_SECOND_IMPORT_SENSOR,
    CONF_UPDATE_FREQUENCY,
    CONF_INPUT_LIST,
    DISCHARGE_ONLY,
    DISCHARGING_RATE,
    DOMAIN,
    FIXED_NUMERICAL_TARIFFS,
    FORCE_DISCHARGE,
    GRID_EXPORT_SIM,
    GRID_IMPORT_SIM,
    GRID_SECOND_EXPORT_SIM,
    GRID_SECOND_IMPORT_SIM,
    MESSAGE_TYPE_BATTERY_UPDATE,
    MESSAGE_TYPE_GENERAL,
    MODE_CHARGING,
    MODE_DISCHARGING,
    MODE_EMPTY,
    MODE_FORCE_CHARGING,
    MODE_FORCE_DISCHARGING,
    MODE_FULL,
    MODE_IDLE,
    NO_TARIFF_INFO,
    OVERIDE_CHARGING,
    PAUSE_BATTERY,
    FIXED_TARIFF,
    TARIFF_TYPE,
    SENSOR_ID,
    SENSOR_TYPE,
    TARIFF_SENSOR,
    CONF_SECOND_ENERGY_IMPORT_TARIFF,
    CONF_SECOND_ENERGY_EXPORT_TARIFF,
    IMPORT,
    EXPORT,
    SIMULATED_SENSOR
)

BATTERY_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_IMPORT_SENSOR): cv.entity_id,
            vol.Required(CONF_EXPORT_SENSOR): cv.entity_id,
            vol.Optional(CONF_ENERGY_TARIFF): cv.entity_id,
            vol.Optional(CONF_ENERGY_EXPORT_TARIFF): cv.entity_id,
            vol.Optional(CONF_ENERGY_IMPORT_TARIFF): cv.entity_id,
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_BATTERY_SIZE): vol.All(float),
            vol.Required(CONF_BATTERY_MAX_DISCHARGE_RATE): vol.All(float),
            vol.Optional(CONF_BATTERY_MAX_CHARGE_RATE, default=1.0): vol.All(float),
            vol.Optional(CONF_BATTERY_EFFICIENCY, default=1.0): vol.All(float),
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({cv.slug: BATTERY_CONFIG_SCHEMA})
    },
    extra=vol.ALLOW_EXTRA
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up battery platforms from a YAML."""
    hass.data.setdefault(DOMAIN, {})

    if config.get(DOMAIN) is None:
        return True

    for battery, conf in config.get(DOMAIN).items():
        _LOGGER.debug("Setup %s.%s", DOMAIN, battery)
        handle = SimulatedBatteryHandle(conf, hass)
        if battery in hass.data[DOMAIN]:
            _LOGGER.warning("Battery name not unique - not able to create.")
            continue

        hass.data[DOMAIN][battery] = handle

        for platform in BATTERY_PLATFORMS:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    platform,
                    DOMAIN,
                    [
                        {
                            CONF_BATTERY: battery,
                            CONF_NAME: conf.get(CONF_NAME, battery)
                        }
                    ],
                    config,
                )
            )
    return True


async def async_setup_entry(hass, entry) -> bool:
    """Set up battery platforms from a Config Flow Entry."""
    hass.data.setdefault(DOMAIN, {})

    _LOGGER.debug("Setup %s.%s", DOMAIN, entry.data[CONF_NAME])

    handle = SimulatedBatteryHandle(entry.data, hass)
    hass.data[DOMAIN][entry.entry_id] = handle

    # Forward the setup to the sensor platform.
    for platform in BATTERY_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    return True


class SimulatedBatteryHandle:
    """Representation of the battery itself."""

    def __init__(self, config, hass):
        """Initialize the Battery."""
        self._hass = hass
        self._date_recording_started = time.asctime()

        self._name = config[CONF_NAME]
        self._battery_size = config[CONF_BATTERY_SIZE]
        self._max_discharge_rate = config[CONF_BATTERY_MAX_DISCHARGE_RATE]
        self._max_charge_rate = config[CONF_BATTERY_MAX_CHARGE_RATE]
        self._battery_efficiency = config[CONF_BATTERY_EFFICIENCY]

        self._sensor_collection: list = []

        self._charging: bool = False

        self._accumulated_import_reading: float = 0.0
        self._last_battery_update_time = time.time()

        self._max_discharge: float = 0.0
        self._charge_percentage: float = 0.0
        self._charge_state: float = 0.0
        self._accumulated_export_reading: float = 0.0
        self._last_import_reading_sensor_data: str = None
        self._last_export_reading_sensor_data: str = None

        if CONF_INPUT_LIST in config:
            self._inputs = config[CONF_INPUT_LIST]
        else:
            """Needed for backwards compatability"""
            self.generate_input_list(config)

        self._switches: dict = {
            OVERIDE_CHARGING: False,
            PAUSE_BATTERY: False,
            FORCE_DISCHARGE: False,
            CHARGE_ONLY: False,
            DISCHARGE_ONLY: False
        }

        self._sensors: dict = {
            ATTR_ENERGY_SAVED: 0.0,
            ATTR_ENERGY_BATTERY_OUT: 0.0,
            ATTR_ENERGY_BATTERY_IN: 0.0,
            CHARGING_RATE: 0.0,
            DISCHARGING_RATE: 0.0,
            ATTR_MONEY_SAVED: 0.0,
            BATTERY_MODE: MODE_IDLE,
            ATTR_MONEY_SAVED_IMPORT: 0.0,
            ATTR_MONEY_SAVED_EXPORT: 0.0,
            BATTERY_CYCLES: 0.0,
        }        
        for input_details in self._inputs:
            self._sensors[input_details[SIMULATED_SENSOR]] = None

        async_at_start(self._hass, self.async_source_tracking)

        async_dispatcher_connect(
            self._hass,
            f"{self._name}-{MESSAGE_TYPE_GENERAL}",
            self.async_reset_battery
        )

    """For backwards compatability with old configs"""
    def generate_input_list(self, config):
        self._tariff_type: str = TARIFF_SENSOR
        if TARIFF_TYPE in config:
            if config[TARIFF_TYPE] == NO_TARIFF_INFO:
                self._tariff_type = NO_TARIFF_INFO
            elif config[TARIFF_TYPE] == FIXED_NUMERICAL_TARIFFS:
                self._tariff_type = FIXED_TARIFF

        self._inputs = [
            {
                SENSOR_ID: config[CONF_IMPORT_SENSOR],
                SENSOR_TYPE: IMPORT,
                SIMULATED_SENSOR: GRID_IMPORT_SIM,
                TARIFF_TYPE: self._tariff_type
            },
            {
                SENSOR_ID: config[CONF_EXPORT_SENSOR],
                SENSOR_TYPE: EXPORT,
                SIMULATED_SENSOR: GRID_EXPORT_SIM,
                TARIFF_TYPE: self._tariff_type
            },
        ]
        if len(config.get(CONF_SECOND_IMPORT_SENSOR, "")) > 6:
            self._inputs.append({
                SENSOR_ID: config[CONF_SECOND_IMPORT_SENSOR],
                SENSOR_TYPE: IMPORT,
                SIMULATED_SENSOR: GRID_SECOND_IMPORT_SIM,
                TARIFF_TYPE: self._tariff_type
            })
        if len(config.get(CONF_SECOND_EXPORT_SENSOR, "")) > 6:
            self._inputs.append({
                SENSOR_ID: config[CONF_SECOND_EXPORT_SENSOR],
                SENSOR_TYPE: EXPORT,
                SIMULATED_SENSOR: GRID_SECOND_EXPORT_SIM,
                TARIFF_TYPE: self._tariff_type
            })

        """Default sensor entities for backwards compatibility"""
        if CONF_ENERGY_IMPORT_TARIFF in config:
            self._inputs[0][self._tariff_type] = config[CONF_ENERGY_IMPORT_TARIFF]
        elif CONF_ENERGY_TARIFF in config:
            """For backwards compatibility"""
            self._inputs[0][self._tariff_type] = config[CONF_ENERGY_TARIFF]

        if CONF_ENERGY_EXPORT_TARIFF in config:
            self._inputs[1][self._tariff_type] = config[CONF_ENERGY_EXPORT_TARIFF]
        if CONF_SECOND_ENERGY_IMPORT_TARIFF in config:
            self._inputs[2][self._tariff_type] = config[CONF_SECOND_ENERGY_IMPORT_TARIFF]
        if CONF_SECOND_ENERGY_EXPORT_TARIFF in config:
            self._inputs[3][self._tariff_type] = config[CONF_SECOND_ENERGY_EXPORT_TARIFF]

    def async_reset_battery(self):
        """Reset the battery to start over."""
        _LOGGER.debug("Reset battery")
        for input in self._inputs:
            self.reset_sim_sensor(
                input[SIMULATED_SENSOR]
            )

        self._charge_state = 0.0

        self._sensors[ATTR_ENERGY_SAVED] = 0.0
        self._sensors[ATTR_MONEY_SAVED] = 0.0
        self._sensors[ATTR_ENERGY_BATTERY_OUT] = 0.0
        self._sensors[ATTR_ENERGY_BATTERY_IN] = 0.0
        self._sensors[ATTR_MONEY_SAVED_IMPORT] = 0.0
        self._sensors[ATTR_MONEY_SAVED_EXPORT] = 0.0

        self._energy_saved_today = 0.0
        self._energy_saved_week = 0.0
        self._energy_saved_month = 0.0

        self._date_recording_started = time.asctime()
        dispatcher_send(
            self._hass,
            f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}"
        )
        return

    def reset_sim_sensor(
        self,
        target_sensor_key
    ):
        """Reset the Simulated Sensor."""
        _LOGGER.debug(f"Reset {target_sensor_key} sim sensor")

        self._sensors[target_sensor_key] = 0.0

        for input_details in self._inputs:
            if input_details[SIMULATED_SENSOR] == target_sensor_key:
                _LOGGER.warning(input_details[SENSOR_ID])
                if self._hass.states.get(input_details[SENSOR_ID]).state not in [
                    STATE_UNAVAILABLE,
                    STATE_UNKNOWN
                ]:
                    self._sensors[target_sensor_key] = float(self._hass.states.get(input_details[SENSOR_ID]).state)

        dispatcher_send(
            self._hass,
            f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}"
        )

    @callback
    def async_source_tracking(self, event):
        """Wait for source to be ready, then start."""

        for input_details in self._inputs:
            """Start tracking state changes for a sensor."""
            listener_handle = async_track_state_change_event(
                self._hass,
                [input_details[SENSOR_ID]],
                self.async_reading_handler
            )
            _LOGGER.debug("(%s) monitoring %s", self._name, input_details[SENSOR_ID])

        _LOGGER.debug(
            "(%s) monitoring %s", self._name, "Done adding the Sensor tracking"
        )
        return

    @callback
    def async_reading_handler(
        self,
        event,
    ):
        sensor_id = event.data.get("entity_id")
        _LOGGER.warning(f"event data {event}")
        for input_details in self._inputs:
            if sensor_id == input_details[SENSOR_ID]: break
        else:
            _LOGGER.warning(f"Error reading input sensor {sensor_id} not found in input sensors")
            return
        
        """Handle the sensor state changes for import or export."""
        sensor_charge_rate = DISCHARGING_RATE if input_details[SENSOR_TYPE] == IMPORT else CHARGING_RATE

        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if (
            old_state is None
            or sensor_id is None
            or new_state is None
            or old_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            or new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
        ):
            # Incorrect Setup or Sensors are not ready
            return

        units = self._hass.states.get(sensor_id).attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        )

        if units in [UnitOfEnergy.KILO_WATT_HOUR, UnitOfEnergy.WATT_HOUR]:
            conversion_factor = (
                1.0 if units == UnitOfEnergy.KILO_WATT_HOUR else 0.001
            )
            unit_of_energy = (
                "kWh" if units == UnitOfEnergy.KILO_WATT_HOUR else "Wh"
            )

        new_state_value = float(new_state.state) * conversion_factor
        old_state_value = float(old_state.state) * conversion_factor

        if  self._sensors[input_details[SIMULATED_SENSOR]] is None:
            self._sensors[input_details[SIMULATED_SENSOR]] = old_state_value

        if new_state_value == old_state_value:
            # _LOGGER.debug("(%s) No change in readings .. ", self._name)
            return

        reading_variance = new_state_value - old_state_value

        _LOGGER.debug(
            f"({self._name}) {sensor_id} {input_details[SENSOR_TYPE]}: {old_state_value} {unit_of_energy} => {new_state_value} {unit_of_energy} = Δ {reading_variance} {unit_of_energy}"
        )

        if reading_variance < 0:
            _LOGGER.warning(
                "(%s) %s sensor value decreased - meter may have been reset",
                self._name,
                input_details[SENSOR_TYPE],
            )
            self._sensors[sensor_charge_rate] = 0
            return

        if input_details[SENSOR_TYPE] is IMPORT:
            self._last_import_reading_sensor_data = input_details
            self._accumulated_import_reading += reading_variance

        if input_details[SENSOR_TYPE] is EXPORT:
            self._last_export_reading_sensor_data = input_details
            self._accumulated_export_reading += reading_variance

        time_since_battery_update = time.time() - self._last_battery_update_time
        if time_since_battery_update > 60:
            self.update_battery(
                self._accumulated_import_reading,
                self._accumulated_export_reading
            )
            self._accumulated_export_reading = 0.0
            self._accumulated_import_reading = 0.0

        return

    def get_tariff_information(self, input_details):
        if input_details is None:
            return None
        """Get Tarrif information to be used for calculating."""
        if input_details[TARIFF_TYPE] == NO_TARIFF_INFO:
            return None
        elif input_details[TARIFF_TYPE] == FIXED_TARIFF:
            return input_details[FIXED_TARIFF]

        # Default behavior - assume sensor entities
        if (
            TARIFF_SENSOR not in input_details
            or input_details[TARIFF_SENSOR] is None
            or len(input_details[TARIFF_SENSOR]) < 6
            or self._hass.states.get(input_details[TARIFF_SENSOR]) is None
            or self._hass.states.get(input_details[TARIFF_SENSOR]).state
            in [STATE_UNAVAILABLE, STATE_UNKNOWN]
        ):
            return None

        return float(self._hass.states.get(input_details[TARIFF_SENSOR]).state)

    def update_battery(self, import_amount, export_amount):
        """Update battery statistics based on the reading for Im- or Export."""
        amount_to_charge: float = 0.0
        amount_to_discharge: float = 0.0
        net_export: float = 0.0
        net_import: float = 0.0

        if self._charge_state == "unknown":
            self._charge_state = 0.0

        """
            Calculate maximum possible charge and discharge based on battery
            specifications and time since last discharge
        """
        time_now = time.time()
        time_last_update = self._last_battery_update_time
        time_since_last_battery_update = time_now - time_last_update

        _LOGGER.debug(
            "(%s) Import: (%s) Export: (%s) .... Timing: %s = Now / %s = Last Update / %s Time (sec).",
            self._name,
            import_amount,
            export_amount,
            time_now,
            time_last_update,
            time_since_last_battery_update,
        )

        max_discharge = time_since_last_battery_update * (
            self._max_discharge_rate / 3600
        )
        max_charge = time_since_last_battery_update * (
            self._max_charge_rate / 3600
        )

        available_capacity_to_charge = (
            self._battery_size - float(self._charge_state)
        )

        available_capacity_to_discharge = float(self._charge_state) * float(
            self._battery_efficiency
        )

        if not any(self._switches.values()):
            _LOGGER.debug("(%s) Battery normal mode.", self._name)

            amount_to_charge = min(
                export_amount, max_charge, available_capacity_to_charge
            )
            amount_to_discharge = min(
                import_amount, max_discharge, available_capacity_to_discharge
            )
            net_import = import_amount - amount_to_discharge
            net_export = export_amount - amount_to_charge
            if amount_to_charge > amount_to_discharge:
                self._sensors[BATTERY_MODE] = MODE_CHARGING
            else:
                self._sensors[BATTERY_MODE] = MODE_DISCHARGING

        elif self._switches[PAUSE_BATTERY]:
            _LOGGER.debug("(%s) Battery paused.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = 0.0
            net_export = export_amount
            net_import = import_amount
            self._sensors[BATTERY_MODE] = MODE_IDLE

        elif self._switches[OVERIDE_CHARGING]:
            _LOGGER.debug("(%s) Battery overide charging.", self._name)
            amount_to_charge = min(max_charge, available_capacity_to_charge)
            amount_to_discharge = 0.0
            net_export = (
                max(export_amount - amount_to_charge, 0)
            )

            net_import = (
                max(amount_to_charge - export_amount, 0) + import_amount
            )
            self._charging = True
            self._sensors[BATTERY_MODE] = MODE_FORCE_CHARGING

        elif self._switches[FORCE_DISCHARGE]:
            _LOGGER.debug("(%s) Battery forced discharging.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = (
                min(max_discharge, available_capacity_to_discharge)
            )
            net_export = (
                max(amount_to_discharge - import_amount, 0) + export_amount
            )
            net_import = max(import_amount - amount_to_discharge, 0)
            self._sensors[BATTERY_MODE] = MODE_FORCE_DISCHARGING

        elif self._switches[CHARGE_ONLY]:
            _LOGGER.debug("(%s) Battery charge only mode.", self._name)
            amount_to_charge: float = min(
                export_amount, max_charge, available_capacity_to_charge
            )
            amount_to_discharge: float = 0.0
            net_import = import_amount
            net_export = export_amount - amount_to_charge
            if amount_to_charge > 0.0:
                self._sensors[BATTERY_MODE] = MODE_CHARGING
            else:
                self._sensors[BATTERY_MODE] = MODE_IDLE

        elif self._switches[DISCHARGE_ONLY]:
            _LOGGER.debug("(%s) Battery discharge only mode.", self._name)
            amount_to_charge: float = 0.0
            amount_to_discharge = min(
                import_amount, max_discharge, available_capacity_to_discharge
            )
            net_import = import_amount - amount_to_discharge
            net_export = export_amount
            if amount_to_discharge > 0.0:
                self._sensors[BATTERY_MODE] = MODE_DISCHARGING
            else:
                self._sensors[BATTERY_MODE] = MODE_IDLE

        current_import_tariff = self.get_tariff_information(
            self._last_import_reading_sensor_data
        )
        current_export_tariff = self.get_tariff_information(
            self._last_export_reading_sensor_data
        )

        if current_import_tariff is not None:
            self._sensors[ATTR_MONEY_SAVED_IMPORT] += (
                import_amount - net_import
            ) * current_import_tariff
        if current_export_tariff is not None:
            self._sensors[ATTR_MONEY_SAVED_EXPORT] += (
                net_export - export_amount
            ) * current_export_tariff
        self._sensors[ATTR_MONEY_SAVED] = (
            self._sensors[ATTR_MONEY_SAVED_IMPORT]
            + self._sensors[ATTR_MONEY_SAVED_EXPORT]
        )
        
        self._charge_state = (
            float(self._charge_state)
            + amount_to_charge
            - (amount_to_discharge / float(self._battery_efficiency))
        )

        self._sensors[ATTR_ENERGY_SAVED] += import_amount - net_import

        if self._last_import_reading_sensor_data is not None:
            self._sensors[self._last_import_reading_sensor_data[SIMULATED_SENSOR]] += net_import
        if self._last_export_reading_sensor_data is not None:
            self._sensors[self._last_export_reading_sensor_data[SIMULATED_SENSOR]] += net_export

        self._sensors[ATTR_ENERGY_BATTERY_IN] += amount_to_charge
        self._sensors[ATTR_ENERGY_BATTERY_OUT] += amount_to_discharge

        self._sensors[CHARGING_RATE] = amount_to_charge / (
            time_since_last_battery_update / 3600
        )
        self._sensors[DISCHARGING_RATE] = amount_to_discharge / (
            time_since_last_battery_update / 3600
        )
        self._sensors[BATTERY_CYCLES] = (
            self._sensors[ATTR_ENERGY_BATTERY_IN] / self._battery_size
        )

        self._charge_percentage = round(
            100 * self._charge_state / self._battery_size
        )

        if self._charge_percentage < 2:
            self._sensors[BATTERY_MODE] = MODE_EMPTY
        elif self._charge_percentage > 98:
            self._sensors[BATTERY_MODE] = MODE_FULL

        """Reset day/week/month counters"""
        if (
            time.strftime("%w")
            != time.strftime("%w", time.gmtime(time_last_update))
        ):
            self._energy_saved_today = 0
        if (
            time.strftime("%U")
            != time.strftime("%U", time.gmtime(time_last_update))
        ):
            self._energy_saved_week = 0
        if (
            time.strftime("%m")
            != time.strftime("%m", time.gmtime(time_last_update))
        ):
            self._energy_saved_month = 0

        self._last_battery_update_time = time_now

        dispatcher_send(
            self._hass,
            f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}"
        )

        _LOGGER.debug("(%s) Battery update complete.", self._name)
