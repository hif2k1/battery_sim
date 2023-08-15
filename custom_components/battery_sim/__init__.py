"""Simulates a battery to evaluate how much energy it could save."""
import logging, time

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import dispatcher_send, async_dispatcher_connect
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import callback

from homeassistant.const import (
    CONF_NAME,
    UnitOfEnergy,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from .const import (
    CONF_BATTERY,
    CONF_BATTERY_EFFICIENCY,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_SIZE,
    CONF_ENERGY_TARIFF,
    CONF_ENERGY_IMPORT_TARIFF,
    CONF_ENERGY_EXPORT_TARIFF,
    CONF_IMPORT_SENSOR,
    CONF_SECOND_IMPORT_SENSOR,
    CONF_SECOND_EXPORT_SENSOR,
    CONF_EXPORT_SENSOR,
    DOMAIN,
    BATTERY_PLATFORMS,
    OVERIDE_CHARGING,
    PAUSE_BATTERY,
    ATTR_ENERGY_SAVED,
    ATTR_ENERGY_BATTERY_OUT,
    ATTR_ENERGY_BATTERY_IN,
    CHARGING_RATE,
    DISCHARGING_RATE,
    GRID_EXPORT_SIM,
    GRID_IMPORT_SIM,
    ATTR_MONEY_SAVED,
    FORCE_DISCHARGE,
    BATTERY_MODE,
    MODE_IDLE,
    MODE_CHARGING,
    MODE_DISCHARGING,
    MODE_FULL,
    MODE_EMPTY,
    MODE_FORCE_DISCHARGING,
    MODE_FORCE_CHARGING,
    ATTR_MONEY_SAVED_IMPORT,
    ATTR_MONEY_SAVED_EXPORT,
    TARIFF_TYPE,
    NO_TARIFF_INFO,
    TARIFF_SENSOR_ENTITIES,
    FIXED_NUMERICAL_TARIFFS,
    BATTERY_CYCLES,
    MESSAGE_TYPE_GENERAL,
    MESSAGE_TYPE_BATTERY_RESET,
    MESSAGE_TYPE_BATTERY_UPDATE,
    CHARGE_ONLY,
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
        self._sensor_collection = []
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
            self._hass, 
            f"{self._name}-{MESSAGE_TYPE_GENERAL}", 
            self.async_reset_battery
        )

        async_dispatcher_connect(
            self._hass,
            f"{self._name}-{MESSAGE_TYPE_BATTERY_RESET}",
            self.reset_sim_sensor,
        )
        
        async_dispatcher_connect(
            self._hass, 
            f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}",
            self.updateBattery
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

        total_sim = sum(
            float(self._hass.states.get(sid).state or 0.0)
            for sid in sensor_ids
            if self._hass.states.get(sid).state
            not in [STATE_UNAVAILABLE, STATE_UNKNOWN]
        )

        self._sensors[target_sensor_key] = total_sim
        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")

    @callback
    def async_source_tracking(self, event):
        """Wait for sources to be ready, then start tracking."""

        def start_sensor_tracking(sensor_id, reading_function, is_import):
            """Start tracking state changes for a sensor."""
            self._sensor_collection.append(
                async_track_state_change_event(
                    self._hass,
                    [sensor_id],
                    lambda event: reading_function(event, is_import),
                )
            )
            _LOGGER.debug("<%s> monitoring %s", self._name, sensor_id)

        start_sensor_tracking(
            self._import_sensor_id, self.async_reading_handler, is_import=True
        )
        start_sensor_tracking(
            self._export_sensor_id, self.async_reading_handler, is_import=False
        )

        if self._second_import_sensor_id is not None:
            start_sensor_tracking(
                self._second_import_sensor_id,
                self.async_reading_handler,
                is_import=True,
            )

        if self._second_export_sensor_id is not None:
            start_sensor_tracking(
                self._second_export_sensor_id,
                self.async_reading_handler,
                is_import=False,
            )

        _LOGGER.debug(
            "<%s> monitoring %s", self._name, "Done adding the Sensor tracking ... "
        )

    @callback
    def async_reading_handler(self, event, is_import):
        """Handle the sensor state changes for import or export."""
        sensor_id = self._import_sensor_id if is_import else self._export_sensor_id
        sensor_type = "import" if is_import else "export"
        sensor_charge_rate = DISCHARGING_RATE if is_import else CHARGING_RATE

        cumulative_reading_attr = f"_last_{sensor_type}_cumulative_reading"
        last_reading_time_attr = f"_last_{sensor_type}_reading_time"
        last_reading_attr = f"_last_{sensor_type}_reading"

        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if not (old_state and new_state):
            return

        units = self._hass.states.get(sensor_id).attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        )

        if units not in [UnitOfEnergy.KILO_WATT_HOUR, UnitOfEnergy.WATT_HOUR]:
            _LOGGER.warning(
                "Units of %s sensor not recognized - may give wrong results",
                sensor_type,
            )

        conversion_factor = 1.0 if units == UnitOfEnergy.KILO_WATT_HOUR else 0.001

        old_state_value = float(old_state.state)
        new_state_value = float(new_state.state)
        
        _LOGGER.debug(f"({self._name}) {sensor_id}: Old = {old_state_value} / New = {new_state_value} ")

        reading_difference = new_state_value - old_state_value

        if reading_difference < 0:
            _LOGGER.warning(
                "%s sensor value decreased - meter may have been reset",
                sensor_type,
            )
            self._sensors[sensor_charge_rate] = 0
            return

        last_reading = getattr(self, last_reading_attr)

        setattr(self, last_reading_time_attr, time.time())

        cumulative_reading = conversion_factor * new_state_value
        rate_reading = conversion_factor * reading_difference

        _LOGGER.debug(
            f"Last Reading Time {self._last_import_reading_time} - {self._last_export_reading_time}"
        )
        
        if self._last_import_reading_time > self._last_export_reading_time:
            if self._last_export_reading > 0:
                _LOGGER.warning("Accumulated reading not cleared error")
                
            last_reading = rate_reading
            
        else:
            last_reading += rate_reading
            import_amount = last_reading if is_import else 0.0
            export_amount = 0.0 if is_import else last_reading
            self.updateBattery(import_amount, export_amount)

        setattr(self, cumulative_reading_attr, cumulative_reading)
        setattr(self, sensor_charge_rate, rate_reading)
        setattr(self, last_reading_attr, last_reading)

    def getTariffReading(self, entity_id):
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
    
    def updateBattery(self, import_amount, export_amount):
        _LOGGER.debug(
            "(%s) Battery update event: Import = %s, Export = %s",
            self._name,
            round(import_amount, 4),
            round(export_amount, 4),
        )
        
        amount_to_charge: float = 0.0
        amount_to_discharge: float = 0.0
        net_export: float = 0.0
        net_import: float = 0.0
        
        if self._charge_state == "unknown":
            self._charge_state = 0.0

        """Calculate maximum possible charge and discharge based on battery specifications and time since last discharge"""
        time_now = time.time()
        time_since_last_battery_update = time_now - self._last_battery_update_time
        max_discharge = time_since_last_battery_update * self._max_discharge_rate / 3600
        max_charge = time_since_last_battery_update * self._max_charge_rate / 3600
        available_capacity_to_charge = self._battery_size - float(self._charge_state)
        available_capacity_to_discharge = float(self._charge_state) * float(
            self._battery_efficiency
        )
        
        if not any(self._switches.values()):
            _LOGGER.debug("Battery (%s) normal mode.", self._name)
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
            _LOGGER.debug("Battery (%s) paused.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = 0.0
            net_export = export_amount
            net_import = import_amount
            self._sensors[BATTERY_MODE] = MODE_IDLE
            
        if self._switches[OVERIDE_CHARGING]:
            _LOGGER.debug("Battery (%s) overide charging.", self._name)
            amount_to_charge = min(max_charge, available_capacity_to_charge)
            amount_to_discharge = 0.0
            net_export = max(export_amount - amount_to_charge, 0)
            net_import = max(amount_to_charge - export_amount, 0) + import_amount
            self._charging = True
            self._sensors[BATTERY_MODE] = MODE_FORCE_CHARGING
            
        if self._switches[FORCE_DISCHARGE]:
            _LOGGER.debug("Battery (%s) forced discharging.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = min(max_discharge, available_capacity_to_discharge)
            net_export = max(amount_to_discharge - import_amount, 0) + export_amount
            net_import = max(import_amount - amount_to_discharge, 0)
            self._sensors[BATTERY_MODE] = MODE_FORCE_DISCHARGING
            
        if self._switches[CHARGE_ONLY]:
            _LOGGER.debug("Battery (%s) charge only mode.", self._name)
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

        current_import_tariff = self.getTariffReading(self._import_tariff_sensor_id)
        current_export_tariff = self.getTariffReading(self._export_tariff_sensor_id)

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
            "%w", time.gmtime(self._last_battery_update_time)
        ):
            self._energy_saved_today = 0
        if time.strftime("%U") != time.strftime(
            "%U", time.gmtime(self._last_battery_update_time)
        ):
            self._energy_saved_week = 0
        if time.strftime("%m") != time.strftime(
            "%m", time.gmtime(self._last_battery_update_time)
        ):
            self._energy_saved_month = 0

        self._last_battery_update_time = time_now
        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")
        _LOGGER.debug(
            "Battery update complete (%s). Sensors: %s", self._name, self._sensors
        )

    # def updateBattery(self, import_amount, export_amount):
    #     _LOGGER.debug(
    #         "Battery update event (%s). Import: %s, Export: %s",
    #         self._name,
    #         round(import_amount, 4),
    #         round(export_amount, 4),
    #     )

    #     def calculate_charge_discharge(
    #         is_charge, max_rate, available_capacity, reading_amount
    #     ):
    #         if is_charge:
    #             return min(reading_amount, max_rate, available_capacity)
    #         else:
    #             return min(reading_amount, max_rate, available_capacity) / float(
    #                 self._battery_efficiency
    #             )
        
    #     if self._charge_state == "unknown":
    #         self._charge_state = 0.0

    #     time_now = time.time()
        
    #     time_since_last_battery_update = time_now - self._last_battery_update_time
        
    #     _LOGGER.debug(f"Last Update: {self._last_battery_update_time} - Now: {time_now} = {time_since_last_battery_update}")
        
    #     max_discharge = time_since_last_battery_update * self._max_discharge_rate / 3600
    #     max_charge = time_since_last_battery_update * self._max_charge_rate / 3600
        
    #     current_import_tariff = self.getTariffReading(self._import_tariff_sensor_id)
    #     current_export_tariff = self.getTariffReading(self._export_tariff_sensor_id)
    
    #     is_charge = self._switches[OVERIDE_CHARGING]
    #     is_discharge = self._switches[FORCE_DISCHARGE]
    #     is_charge_only = self._switches[CHARGE_ONLY]    
    #     is_paused = self._switches[PAUSE_BATTERY]
        
    #     _LOGGER.debug("Battery (%s): Is Force Charging: %s ", self._name, is_charge)
    #     _LOGGER.debug("Battery (%s): Is Force Discharging: %s ", self._name,  is_discharge)
    #     _LOGGER.debug("Battery (%s): Is Charge Only: %s", self._name,  is_charge_only)
    #     _LOGGER.debug("Battery (%s): Is Paused: %s", self._name,  is_paused)
        
    #     _LOGGER.debug("Battery (%s): %s", self._name, self._sensors)

    #     if is_paused:          
    #         self._sensors[BATTERY_MODE] = MODE_IDLE
    #         self._sensors[GRID_IMPORT_SIM] += import_amount
    #         self._sensors[GRID_EXPORT_SIM] += export_amount
    #         self._sensors[ATTR_ENERGY_BATTERY_IN] += 0.0
    #         self._sensors[ATTR_ENERGY_BATTERY_OUT] += 0.0
    #         self._sensors[CHARGING_RATE] = 0.0 
    #         self._sensors[DISCHARGING_RATE] = 0.0 

    #     else:
    #         if self._sensors[CHARGING_RATE] <= 0:
    #             self._sensors[BATTERY_MODE] = MODE_EMPTY
            
    #         amount_to_charge = calculate_charge_discharge(
    #             is_charge,
    #             max_charge,
    #             self._battery_size - float(self._charge_state),
    #             export_amount,
    #         )

    #         amount_to_discharge = calculate_charge_discharge(
    #             is_discharge,
    #             max_discharge,
    #             float(self._charge_state) * float(self._battery_efficiency),
    #             import_amount,
    #         )
            
    #         _LOGGER.debug(
    #             "Battery update event (%s). Amount to Charge: %s, Amount to Discharge: %s",
    #             self._name,
    #             round(amount_to_charge, 4),
    #             round(amount_to_discharge, 4),
    #         )

    #         net_export = max(amount_to_discharge - import_amount, 0) + export_amount
    #         net_import = max(import_amount - amount_to_discharge, 0)
            
    #         _LOGGER.debug(
    #             "Battery update event (%s). Net Import: %s, Net Export: %s",
    #             self._name,
    #             round(net_import, 4),
    #             round(net_export, 4),
    #         )

    #         if is_charge_only:
    #             self._sensors[BATTERY_MODE] = (
    #                 MODE_CHARGING
    #                 if amount_to_charge > amount_to_discharge
    #                 else MODE_IDLE
    #             )
    #         else:
    #             self._sensors[BATTERY_MODE] = (
    #                 MODE_CHARGING
    #                 if amount_to_charge > amount_to_discharge
    #                 else MODE_DISCHARGING
    #             )

    #         if current_import_tariff is not None:
    #             self._sensors[ATTR_MONEY_SAVED_IMPORT] += (
    #                 import_amount - net_import
    #             ) * current_import_tariff
    #         if current_export_tariff is not None:
    #             self._sensors[ATTR_MONEY_SAVED_EXPORT] += (
    #                 net_export - export_amount
    #             ) * current_export_tariff

    #         if self._tariff_type is not NO_TARIFF_INFO:
    #             self._sensors[ATTR_MONEY_SAVED] = (
    #                 self._sensors[ATTR_MONEY_SAVED_IMPORT]
    #                 + self._sensors[ATTR_MONEY_SAVED_EXPORT]
    #             )

    #         self._charge_state += amount_to_charge - amount_to_discharge

    #         self._sensors[ATTR_ENERGY_SAVED] += import_amount - net_import
    #         self._sensors[GRID_IMPORT_SIM] += net_import
    #         self._sensors[GRID_EXPORT_SIM] += net_export
    #         self._sensors[ATTR_ENERGY_BATTERY_IN] += amount_to_charge
    #         self._sensors[ATTR_ENERGY_BATTERY_OUT] += amount_to_discharge

    #         self._sensors[CHARGING_RATE] = amount_to_charge / (
    #             time_since_last_battery_update / 3600
    #         )
    #         self._sensors[DISCHARGING_RATE] = amount_to_discharge / (
    #             time_since_last_battery_update / 3600
    #         )
    #         self._sensors[BATTERY_CYCLES] = (
    #             self._sensors[ATTR_ENERGY_BATTERY_IN] / self._battery_size
    #         )

    #         self._charge_percentage = round(100 * self._charge_state / self._battery_size)
            
    #         _LOGGER.debug(f"Battery State ({self._name}): {self._charge_percentage}% ")

    #         if self._charge_percentage < 2:
    #             self._sensors[BATTERY_MODE] = MODE_EMPTY
    #         elif self._charge_percentage > 98:
    #             self._sensors[BATTERY_MODE] = MODE_FULL
                
    #         _LOGGER.debug(f"Battery State ({self._name}): {self._charge_percentage}% @ {self._sensors[BATTERY_MODE]} ")
            
    #         last_update_battery = self._last_battery_update_time

    #         # if last_update_battery.weekday() != time_now.weekday():
    #         #     self._energy_saved_today = 0
    #         # if last_update_battery.isocalendar()[1] != time_now.isocalendar()[1]:
    #         #     self._energy_saved_week = 0
    #         # if last_update_battery.month != time_now.month:
    #         #     self._energy_saved_month = 0
                
    #         self._last_battery_update_time = time_now

    #     _LOGGER.debug(
    #         "Battery update complete (%s). Sensors: %s", self._name, self._sensors
    #     )

    #     dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")
