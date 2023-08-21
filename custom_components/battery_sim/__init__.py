"""Simulates a battery to evaluate how much energy it could save."""
import logging, time

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.dispatcher import dispatcher_send, async_dispatcher_connect

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
    DISCHARGING_RATE,
    DOMAIN,
    FIXED_NUMERICAL_TARIFFS,
    FORCE_DISCHARGE,
    GRID_EXPORT_SIM,
    GRID_IMPORT_SIM,
    MESSAGE_TYPE_BATTERY_RESET_IMP,
    MESSAGE_TYPE_BATTERY_RESET_EXP,
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
    TARIFF_SENSOR_ENTITIES,
    TARIFF_TYPE,
)

_LOGGER = logging.getLogger(__name__)

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
    {DOMAIN: vol.Schema({cv.slug: BATTERY_CONFIG_SCHEMA})}, extra=vol.ALLOW_EXTRA
)


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
                    [{CONF_BATTERY: battery, CONF_NAME: conf.get(CONF_NAME, battery)}],
                    config,
                )
            )
    return True


async def async_setup_entry(hass, entry) -> bool:
    """Set up battery platforms from a Config Flow Entry"""
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
    """Representation of the battery itself"""

    def __init__(self, config, hass):
        """Initialize the Battery."""
        self._hass = hass
        self._import_sensor_id = config[CONF_IMPORT_SENSOR]
        self._export_sensor_id = config[CONF_EXPORT_SENSOR]

        self._second_import_sensor_id = (
            config.get(CONF_SECOND_IMPORT_SENSOR)
            if len(config.get(CONF_SECOND_IMPORT_SENSOR, "")) > 6
            else None
        )

        self._second_export_sensor_id = (
            config.get(CONF_SECOND_EXPORT_SENSOR)
            if len(config.get(CONF_SECOND_EXPORT_SENSOR, "")) > 6
            else None
        )

        self._second_import_configured = bool(self._second_import_sensor_id)
        self._second_export_configured = bool(self._second_export_sensor_id)

        """Defalt to sensor entites for backwards compatibility"""
        self._tariff_type = TARIFF_SENSOR_ENTITIES

        if TARIFF_TYPE in config:
            self._tariff_type = config[TARIFF_TYPE]

        self._import_tariff_sensor_id = None
        if CONF_ENERGY_IMPORT_TARIFF in config:
            self._import_tariff_sensor_id = config[CONF_ENERGY_IMPORT_TARIFF]
        elif CONF_ENERGY_TARIFF in config:
            """For backwards compatibility"""
            self._import_tariff_sensor_id = config[CONF_ENERGY_TARIFF]

        self._export_tariff_sensor_id = None
        if CONF_ENERGY_EXPORT_TARIFF in config:
            self._export_tariff_sensor_id = config[CONF_ENERGY_EXPORT_TARIFF]

        self._date_recording_started = time.asctime()
        self._import_collection_primary = None
        self._export_collection_primary = None
        
        self._import_collection_secondary = None
        self._export_collection_secondary = None
        self._charging = False

        self._name = config[CONF_NAME]
        self._battery_size = config[CONF_BATTERY_SIZE]
        self._max_discharge_rate = config[CONF_BATTERY_MAX_DISCHARGE_RATE]
        self._max_charge_rate = config[CONF_BATTERY_MAX_CHARGE_RATE]
        self._battery_efficiency = config[CONF_BATTERY_EFFICIENCY]

        self._last_import_reading_time = time.time()
        self._last_export_reading_time = time.time()
        self._last_battery_update_time = time.time()

        self._max_discharge = 0.0
        self._charge_percentage = 0.0
        self._charge_state = 0.0
        self._last_export_reading = 0.0
        self._last_import_cumulative_reading = 1.0

        self._switches = {
            OVERIDE_CHARGING: False,
            PAUSE_BATTERY: False,
            FORCE_DISCHARGE: False,
            CHARGE_ONLY: False,
        }

        self._sensors = {
            ATTR_ENERGY_SAVED: 0.0,
            ATTR_ENERGY_BATTERY_OUT: 0.0,
            ATTR_ENERGY_BATTERY_IN: 0.0,
            CHARGING_RATE: 0.0,
            DISCHARGING_RATE: 0.0,
            GRID_EXPORT_SIM: 0.0,
            GRID_IMPORT_SIM: 0.0,
            ATTR_MONEY_SAVED: 0.0,
            BATTERY_MODE: MODE_IDLE,
            ATTR_MONEY_SAVED_IMPORT: 0.0,
            ATTR_MONEY_SAVED_EXPORT: 0.0,
            BATTERY_CYCLES: 0.0,
        }

        async_at_start(self._hass, self.async_source_tracking)

        async_dispatcher_connect(
            self._hass, f"{self._name}-{MESSAGE_TYPE_GENERAL}", self.async_reset_battery
        )

        async_dispatcher_connect(
            self._hass,
            f"{self._name}-{MESSAGE_TYPE_BATTERY_RESET_IMP}",
            self.reset_sim_sensor,
        )

        async_dispatcher_connect(
            self._hass,
            f"{self._name}-{MESSAGE_TYPE_BATTERY_RESET_EXP}",
            self.reset_sim_sensor,
        )

        async_dispatcher_connect(
            self._hass,
            f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}",
            self.update_battery,
        )

    def async_reset_battery(self):
        _LOGGER.debug("Reset battery")
        self.reset_sim_sensor(
            GRID_IMPORT_SIM, self._import_sensor_id, self._second_import_sensor_id
        )
        self.reset_sim_sensor(
            GRID_EXPORT_SIM, self._export_sensor_id, self._second_export_sensor_id
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
        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")

    def reset_sim_sensor(
        self, target_sensor_key, primary_sensor_id, secondary_sensor_id
    ):
        _LOGGER.debug(f"Reset {target_sensor_key} sim sensor")

        sensor_ids = [primary_sensor_id]

        if secondary_sensor_id is not None:
            sensor_ids.append(secondary_sensor_id)

        total_sim = 0.0

        for sid in sensor_ids:
            if self._hass.states.get(sid).state not in [
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ]:
                total_sim += float(self._hass.states.get(sid).state)

        self._sensors[target_sensor_key] = total_sim
        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")

    @callback
    def async_source_tracking(self, event):
        """Wait for source to be ready, then start."""
        def start_sensor_tracking(sensor_id, collection, reading_function, is_import):
            """Start tracking state changes for a sensor."""
            setattr( 
                self, 
                collection,
                async_track_state_change_event(
                    self._hass,
                    [sensor_id],
                    lambda event: reading_function(event, is_import),
                )
            )
            
            _LOGGER.debug("(%s) monitoring %s", self._name, sensor_id)

        start_sensor_tracking(
            sensor_id = self._import_sensor_id, 
            collection = '_import_collection_primary',
            reading_function= self.async_reading_handler, 
            is_import=True
        )
        
        start_sensor_tracking(
            sensor_id = self._export_sensor_id, 
            collection = '_export_collection_primary',
            reading_function= self.async_reading_handler, 
            is_import=True
        )

        if self._second_import_sensor_id is not None:
            start_sensor_tracking(
                sensor_id = self._second_import_sensor_id, 
                collection = '_import_collection_secondary',
                reading_function= self.async_reading_handler, 
                is_import=True
            )
            
        if self._second_import_sensor_id is not None:
            start_sensor_tracking(
                sensor_id = self._second_export_sensor_id, 
                collection = '_export_collection_secondary',
                reading_function= self.async_reading_handler, 
                is_import=False
            )  

        _LOGGER.debug(
            "(%s) monitoring %s", self._name, "Done adding the Sensor tracking ... "
        )

    @callback
    def async_reading_handler(self, event, is_import):
        """Handle the sensor state changes for import or export."""
        sensor_charge_rate = DISCHARGING_RATE if is_import else CHARGING_RATE
        sensor_type = "import" if is_import else "export"

        cumulative_reading_attr = f"_last_{sensor_type}_cumulative_reading"
        last_reading_time_attr = f"_last_{sensor_type}_reading_time"
        last_reading_attr = f"_last_{sensor_type}_reading"
        
        last_reading_time = time.time()

        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        sensor_id = event.data.get("entity_id")

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

        # TODO: Find logic to determine this once at Initialization
        if units not in [UnitOfEnergy.KILO_WATT_HOUR, UnitOfEnergy.WATT_HOUR]:
            _LOGGER.warning(
                "Units of %s sensor not recognized - may give wrong results",
                sensor_type,
            )

        # TODO: Find logic to determine this once at Initialization
        conversion_factor = 1.0 if units == UnitOfEnergy.KILO_WATT_HOUR else 0.001
        unit_of_energy = 'kWh' if units == UnitOfEnergy.KILO_WATT_HOUR else 'wH'

        # TODO: Find logic to determine this once at Initialization (Conversion factor)
        new_state_value = float(new_state.state) * conversion_factor
        old_state_value = float(old_state.state) * conversion_factor


        if new_state_value == old_state_value:
            # _LOGGER.debug("(%s) No change in readings .. ", self._name)
            return

        reading_variance = new_state_value - old_state_value

        _LOGGER.debug(
            f"({self._name}) {sensor_id} {is_import}: {old_state_value} {unit_of_energy} => {new_state_value} {unit_of_energy} = Δ {reading_variance} {unit_of_energy}"
        )

        if reading_variance < 0:
            _LOGGER.warning(
                "(%s) %s sensor value decreased - meter may have been reset",
                self._name,
                sensor_type,
            )
            self._sensors[sensor_charge_rate] = 0

        if reading_variance >= 0:
            setattr(self, cumulative_reading_attr, new_state_value)

            if is_import:
                self.update_battery(reading_variance, self._last_export_reading)
                self._last_export_reading = 0.0

            if not is_import:
                if self._last_import_reading_time > self._last_export_reading_time:
                    if self._last_export_reading > 0:
                        _LOGGER.warning(
                            "(%s) Accumulated export reading not cleared error = ",
                            self._last_export_reading,
                        )

                    self._last_export_reading = reading_variance

                else:
                    reading_variance += self._last_export_reading
                    self._last_export_reading = 0.0
                    self.update_battery(0.0, reading_variance)

        # Finish the Sensor Reading
        setattr(self, last_reading_time_attr, last_reading_time)
        return

    def get_tarrif_information(self, entity_id):
        if self._tariff_type == NO_TARIFF_INFO:
            return None
        elif self._tariff_type == FIXED_NUMERICAL_TARIFFS:
            return entity_id

        # Default behavior - assume sensor entities
        if (
            entity_id is None
            or len(entity_id) < 6
            or self._hass.states.get(entity_id) is None
            or self._hass.states.get(entity_id).state
            in [STATE_UNAVAILABLE, STATE_UNKNOWN]
        ):
            return None

        return float(self._hass.states.get(entity_id).state)

    def update_battery(self, import_amount, export_amount):
        """ Update battery statistics based on the reading for Import or Export """
        amount_to_charge: float = 0.0
        amount_to_discharge: float = 0.0
        net_export: float = 0.0
        net_import: float = 0.0

        if self._charge_state == "unknown":
            self._charge_state = 0.0

        """Calculate maximum possible charge and discharge based on battery specifications and time since last discharge"""
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

        max_discharge = time_since_last_battery_update * self._max_discharge_rate / 3600
        max_charge = time_since_last_battery_update * self._max_charge_rate / 3600

        available_capacity_to_charge = self._battery_size - float(self._charge_state)
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

        if self._switches[PAUSE_BATTERY]:
            _LOGGER.debug("(%s) Battery paused.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = 0.0
            net_export = export_amount
            net_import = import_amount
            self._sensors[BATTERY_MODE] = MODE_IDLE

        if self._switches[OVERIDE_CHARGING]:
            _LOGGER.debug("(%s) Battery overide charging.", self._name)
            amount_to_charge = min(max_charge, available_capacity_to_charge)
            amount_to_discharge = 0.0
            net_export = max(export_amount - amount_to_charge, 0)
            net_import = max(amount_to_charge - export_amount, 0) + import_amount
            self._charging = True
            self._sensors[BATTERY_MODE] = MODE_FORCE_CHARGING

        if self._switches[FORCE_DISCHARGE]:
            _LOGGER.debug("(%s) Battery forced discharging.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = min(max_discharge, available_capacity_to_discharge)
            net_export = max(amount_to_discharge - import_amount, 0) + export_amount
            net_import = max(import_amount - amount_to_discharge, 0)
            self._sensors[BATTERY_MODE] = MODE_FORCE_DISCHARGING

        if self._switches[CHARGE_ONLY]:
            _LOGGER.debug("(%s) Battery charge only mode.", self._name)
            amount_to_charge: float = min(
                export_amount, max_charge, available_capacity_to_charge
            )
            
            amount_to_discharge: float = 0.0
            net_import = import_amount
            net_export = export_amount - amount_to_charge
            if amount_to_charge > amount_to_discharge:
                self._sensors[BATTERY_MODE] = MODE_CHARGING
            else:
                self._sensors[BATTERY_MODE] = MODE_IDLE

        current_import_tariff = self.get_tarrif_information(
            self._import_tariff_sensor_id
        )
        current_export_tariff = self.get_tarrif_information(
            self._export_tariff_sensor_id
        )

        if current_import_tariff is not None:
            self._sensors[ATTR_MONEY_SAVED_IMPORT] += (
                import_amount - net_import
            ) * current_import_tariff
        if current_export_tariff is not None:
            self._sensors[ATTR_MONEY_SAVED_EXPORT] += (
                net_export - export_amount
            ) * current_export_tariff
        if self._tariff_type is not NO_TARIFF_INFO:
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
        self._sensors[GRID_IMPORT_SIM] += net_import
        self._sensors[GRID_EXPORT_SIM] += net_export
        self._sensors[ATTR_ENERGY_BATTERY_IN] += amount_to_charge
        self._sensors[ATTR_ENERGY_BATTERY_OUT] += amount_to_discharge

        # BUG: Charging Rate = 8 kWh (at setting with 8 kWh) but this isn't correct.
        #       - PV can max output 5kWh
        #       - Check calculation.
        self._sensors[CHARGING_RATE] = amount_to_charge / (
            time_since_last_battery_update / 3600
        )
        self._sensors[DISCHARGING_RATE] = amount_to_discharge / (
            time_since_last_battery_update / 3600
        )
        self._sensors[BATTERY_CYCLES] = (
            self._sensors[ATTR_ENERGY_BATTERY_IN] / self._battery_size
        )

        self._charge_percentage = round(100 * self._charge_state / self._battery_size)

        if self._charge_percentage < 2:
            self._sensors[BATTERY_MODE] = MODE_EMPTY
        elif self._charge_percentage > 98:
            self._sensors[BATTERY_MODE] = MODE_FULL

        """Reset day/week/month counters"""
        if time.strftime("%w") != time.strftime(
            "%w", time.gmtime(time_last_update)
        ):
            self._energy_saved_today = 0
        if time.strftime("%U") != time.strftime(
            "%U", time.gmtime(time_last_update)
        ):
            self._energy_saved_week = 0
        if time.strftime("%m") != time.strftime( 
            "%m", time.gmtime(time_last_update)
        ):
            self._energy_saved_month = 0

        self._last_battery_update_time = time_now
        
        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")
        
        _LOGGER.debug(
            "(%s) Battery update complete.", self._name
        )

    def update_battery_new(self, import_amount, export_amount):
        time_now = time.time()
        time_last_update = self._last_battery_update_time
        time_since_last_battery_update = time_now - time_last_update

        # Calculate maximum possible charge and discharge
        max_discharge = time_since_last_battery_update * self._max_discharge_rate / 3600
        max_charge = time_since_last_battery_update * self._max_charge_rate / 3600

        # Initialize variables
        amount_to_charge = 0.0
        amount_to_discharge = 0.0
        net_export = 0.0
        net_import = 0.0
        current_import_tariff = self.get_tarrif_information(self._import_tariff_sensor_id)
        current_export_tariff = self.get_tarrif_information(self._export_tariff_sensor_id)

        # Update battery mode
        battery_mode = MODE_IDLE  # Default mode

        if not any(self._switches.values()):
            amount_to_charge = min(export_amount, max_charge, self._battery_size - self._charge_state)
            amount_to_discharge = min(import_amount, max_discharge, self._charge_state * self._battery_efficiency)
            net_import = import_amount - amount_to_discharge
            net_export = export_amount - amount_to_charge
            battery_mode = MODE_CHARGING if amount_to_charge > amount_to_discharge else MODE_DISCHARGING

        elif self._switches[PAUSE_BATTERY]:
            net_export = export_amount
            net_import = import_amount
            battery_mode = MODE_IDLE

        elif self._switches[OVERIDE_CHARGING]:
            amount_to_charge = min(max_charge, self._battery_size - self._charge_state)
            net_export = max(export_amount - amount_to_charge, 0)
            net_import = max(amount_to_charge - export_amount, 0) + import_amount
            self._charging = True
            battery_mode = MODE_FORCE_CHARGING

        elif self._switches[FORCE_DISCHARGE]:
            amount_to_discharge = min(max_discharge, available_capacity_to_discharge)
            net_export = max(amount_to_discharge - import_amount, 0) + export_amount
            net_import = max(import_amount - amount_to_discharge, 0)
            battery_mode = MODE_FORCE_DISCHARGING

        elif self._switches[CHARGE_ONLY]:
            amount_to_charge: float = min( export_amount, max_charge, available_capacity_to_charge )
            net_import = import_amount
            net_export = export_amount - amount_to_charge
            if amount_to_charge > amount_to_discharge:
                self._sensors[BATTERY_MODE] = MODE_CHARGING
            else:
                self._sensors[BATTERY_MODE] = MODE_IDLE
        
        else:
            return

        # Update cost savings based on tariff information
        if current_import_tariff is not None:
            self._sensors[ATTR_MONEY_SAVED_IMPORT] += (import_amount - net_import) * current_import_tariff
        if current_export_tariff is not None:
            self._sensors[ATTR_MONEY_SAVED_EXPORT] += (net_export - export_amount) * current_export_tariff
        if self._tariff_type is not NO_TARIFF_INFO:
            self._sensors[ATTR_MONEY_SAVED] = self._sensors[ATTR_MONEY_SAVED_IMPORT] + self._sensors[ATTR_MONEY_SAVED_EXPORT]

        # Update sensor values
        self._sensors[GRID_IMPORT_SIM] += net_import
        self._sensors[GRID_EXPORT_SIM] += net_export
        self._sensors[ATTR_ENERGY_SAVED] += import_amount - net_import
        self._sensors[ATTR_ENERGY_BATTERY_IN] += amount_to_charge
        self._sensors[ATTR_ENERGY_BATTERY_OUT] += amount_to_discharge
        
        self._sensors[CHARGING_RATE] = amount_to_charge / (time_since_last_battery_update / 3600)
        self._sensors[DISCHARGING_RATE] = amount_to_discharge / (time_since_last_battery_update / 3600)

        #TODO: How is a cycle defined, if you stop at 20% and 80% it will significalty improve the life
        self._sensors[BATTERY_CYCLES] = self._sensors[ATTR_ENERGY_BATTERY_IN] / self._battery_size
        
        self._charge_state += amount_to_charge - (amount_to_discharge / self._battery_efficiency)
        self._charge_percentage = round(100 * self._charge_state / self._battery_size)

        # Update battery mode based on charge percentage
        if self._charge_percentage < 2:
            battery_mode = MODE_EMPTY
        elif self._charge_percentage > 98:
            battery_mode = MODE_FULL

        # Reset day/week/month counters
        if time.strftime("%w", time_now) != time.strftime("%w", time.gmtime(time_last_update)):
            self._energy_saved_today = 0
        if time.strftime("%U", time_now) != time.strftime("%U", time.gmtime(time_last_update)):
            self._energy_saved_week = 0
        if time.strftime("%m", time_now) != time.strftime("%m", time.gmtime(time_last_update)):
            self._energy_saved_month = 0

        # Update last battery update time
        self._last_battery_update_time = time_now

        # Send update signal
        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")
        _LOGGER.debug("(%s) Battery update complete.", self._name)
