"""Simulates a battery to evaluate how much energy it could save."""
import logging, time

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import dispatcher_send, async_dispatcher_connect
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import callback

from homeassistant.const import (
    CONF_NAME,
    ENERGY_WATT_HOUR,
    ENERGY_KILO_WATT_HOUR,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EVENT_HOMEASSISTANT_START
)

from .const import (
    CONF_BATTERY,
    CONF_BATTERY_EFFICIENCY,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_SIZE,
    CONF_ENERGY_TARIFF,
    CONF_IMPORT_SENSOR,
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
    ATTR_MONEY_SAVED
)

_LOGGER = logging.getLogger(__name__)

BATTERY_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_IMPORT_SENSOR): cv.entity_id,
            vol.Required(CONF_EXPORT_SENSOR): cv.entity_id,
            vol.Optional(CONF_ENERGY_TARIFF): cv.entity_id,
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
    """Set up platform from a YAML."""
    hass.data.setdefault(DOMAIN, {})

    if config.get(DOMAIN)!= None:
        for battery, conf in config.get(DOMAIN).items():
            _LOGGER.debug("Setup %s.%s", DOMAIN, battery)
            handle = SimulatedBatteryHandle(conf, hass)
            if (battery in hass.data[DOMAIN]):
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
    """Set up platform from a ConfigEntry."""
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

class SimulatedBatteryHandle():
    """Representation of the battery itself"""

    def __init__(
        self,
        config,
        hass
    ):

        """Initialize the Battery."""
        self._hass = hass
        self._import_sensor_id = config[CONF_IMPORT_SENSOR]
        self._export_sensor_id = config[CONF_EXPORT_SENSOR]
        if CONF_ENERGY_TARIFF not in config:
            self._tariff_sensor_id = "none"
        else:
            self._tariff_sensor_id = config[CONF_ENERGY_TARIFF]
        self._date_recording_started = time.asctime()
        self._collecting1 = None
        self._collecting2 = None
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
            PAUSE_BATTERY: False 
            }
        self._sensors = {
            ATTR_ENERGY_SAVED: 0.0,
            ATTR_ENERGY_BATTERY_OUT: 0.0,
            ATTR_ENERGY_BATTERY_IN: 0.0, 
            CHARGING_RATE: 0.0,
            DISCHARGING_RATE: 0.0,
            GRID_EXPORT_SIM: 0.0,
            GRID_IMPORT_SIM: 0.0,
            ATTR_MONEY_SAVED: 0.0
        }
        self._energy_saved_today = 0.0
        self._energy_saved_week = 0.0
        self._energy_saved_month = 0.0

        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self.async_source_tracking
        )
        async_dispatcher_connect(
            self._hass, f"{self._name}-BatteryResetMessage", self.async_reset_battery
        )
        async_dispatcher_connect(
            self._hass, f"{self._name}-BatteryResetImportSim", self.reset_import_sim_sensor
        )
        async_dispatcher_connect(
            self._hass, f"{self._name}-BatteryResetExportSim", self.reset_export_sim_sensor
        )

    def async_reset_battery(self):
        self.reset_import_sim_sensor()
        self.reset_export_sim_sensor()
        self._charge_state = 0.0
        self._sensors[ATTR_ENERGY_SAVED] = 0.0
        self._sensors[ATTR_MONEY_SAVED] = 0.0
        self._energy_saved_today = 0.0
        self._energy_saved_week = 0.0
        self._energy_saved_month = 0.0
        self._date_recording_started = time.asctime()
        dispatcher_send(self._hass, f"{self._name}-BatteryUpdateMessage")
        return

    def reset_import_sim_sensor(self):
        if (self._hass.states.get(self._import_sensor_id).state is not None and
            self._hass.states.get(self._import_sensor_id).state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]):
            self._sensors[GRID_IMPORT_SIM] = float(self._hass.states.get(self._import_sensor_id).state)
        else:
            self._sensors[GRID_IMPORT_SIM] = 0.0
        dispatcher_send(self._hass, f"{self._name}-BatteryUpdateMessage")

    def reset_export_sim_sensor(self):
        _LOGGER.debug("Reset export sim sensor")
        if (self._hass.states.get(self._export_sensor_id).state is not None and
            self._hass.states.get(self._export_sensor_id).state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]):
            self._sensors[GRID_EXPORT_SIM] = float(self._hass.states.get(self._export_sensor_id).state)
        else:
            self._sensors[GRID_EXPORT_SIM] = 0.0
        dispatcher_send(self._hass, f"{self._name}-BatteryUpdateMessage")

    @callback
    def async_source_tracking(self, event):
        """Wait for source to be ready, then start."""

        _LOGGER.debug("<%s> monitoring %s", self._name, self._import_sensor_id)
        self._collecting1 = async_track_state_change_event(
            self._hass, [self._import_sensor_id], self.async_import_reading
        )
        _LOGGER.debug("<%s> monitoring %s", self._name, self._export_sensor_id)
        self._collecting2 = async_track_state_change_event(
            self._hass, [self._export_sensor_id], self.async_export_reading
        )

    @callback
    def async_export_reading(self, event):

        """Handle the sensor state changes."""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if (
            old_state is None
            or new_state is None
            or old_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            or new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
        ):
            return

        conversion_factor = 1.0
        units = self._hass.states.get(self._export_sensor_id).attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if units == ENERGY_WATT_HOUR:
            conversion_factor = 0.001
        elif units == ENERGY_KILO_WATT_HOUR:
            conversion_factor = 1.0
        else:
            _LOGGER.warning("Units of import sensor not recognised - may give wrong results")

        export_amount = conversion_factor*(float(new_state.state) - float(old_state.state))

        if export_amount < 0:
            _LOGGER.warning("Export sensor value decreased - meter may have been reset")
            self._sensors[CHARGING_RATE] = 0
            self._last_export_reading_time = time.time()
            return

        if (self._last_import_reading_time>self._last_export_reading_time):
            if (self._last_export_reading > 0):
                _LOGGER.warning("Accumulated export reading not cleared error")
            self._last_export_reading = export_amount
        else:
            export_amount += self._last_export_reading
            self._last_export_reading = 0.0
            self.updateBattery(0.0, export_amount)
        self._last_export_reading_time = time.time()

    @callback
    def async_import_reading(self, event):

        """Handle the import sensor state changes - energy being imported from grid to be drawn from battery instead"""
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        """If data missing return"""
        if (
            old_state is None
            or new_state is None
            or old_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            or new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
        ):
            return

        self._last_import_reading_time = time.time()

        """Check units of import sensor and calculate import amount in kWh"""
        conversion_factor = 1.0
        units = self._hass.states.get(self._import_sensor_id).attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if units == ENERGY_WATT_HOUR:
            conversion_factor = 0.001
        elif units == ENERGY_KILO_WATT_HOUR:
            conversion_factor = 1
        else:
            _LOGGER.warning("Units of import sensor not recognised - may give wrong results")
        import_amount = conversion_factor*(float(new_state.state) - float(old_state.state))
        self._last_import_cumulative_reading = conversion_factor*(float(new_state.state))

        if import_amount < 0:
            _LOGGER.warning("Import sensor value decreased - meter may have been reset")
            self._sensors[DISCHARGING_RATE] = 0
            return

        self.updateBattery(import_amount, self._last_export_reading)
        self._last_export_reading = 0.0
    
    def updateBattery(self, import_amount, export_amount):
        _LOGGER.debug("Battery update event (%s). Import: %s, Export: %s", self._name, round(import_amount,4), round,(export_amount,4))
        if self._charge_state=='unknown': self._charge_state = 0.0

        """Calculate maximum possible discharge based on battery specifications and time since last discharge"""
        time_now = time.time()
        time_since_last_battery_update = time_now-self._last_battery_update_time
        max_discharge = time_since_last_battery_update*self._max_discharge_rate/3600
        max_charge = time_since_last_battery_update*self._max_charge_rate/3600
        available_capacity_to_charge = self._battery_size - float(self._charge_state)
        available_capacity_to_discharge = float(self._charge_state)*float(self._battery_efficiency)

        if self._switches[PAUSE_BATTERY]:
            _LOGGER.debug("Battery (%s) paused.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = 0.0
            net_export = export_amount
            net_import = import_amount
            net_money_saved = 0.0
        elif self._switches[OVERIDE_CHARGING]:
            _LOGGER.debug("Battery (%s) overide charging.", self._name)
            amount_to_charge = min(max_charge, available_capacity_to_charge)
            amount_to_discharge = 0.0
            net_export = max(export_amount - amount_to_charge, 0)
            net_import = max(amount_to_charge - export_amount, 0) + import_amount
            if self._tariff_sensor_id != "none":
                net_money_saved = -1*amount_to_charge*float(self._hass.states.get(self._tariff_sensor_id).state)
        else:
            _LOGGER.debug("Battery (%s) normal mode.", self._name)
            amount_to_charge = min(export_amount, max_charge, available_capacity_to_charge)
            amount_to_discharge = min(import_amount, max_discharge, available_capacity_to_discharge)
            net_import = import_amount - amount_to_discharge
            net_export = export_amount - amount_to_charge
            if (self._tariff_sensor_id != "none" and
                self._hass.states.get(self._tariff_sensor_id).state is not None and
                self._hass.states.get(self._tariff_sensor_id).state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]):
                net_money_saved = amount_to_discharge*float(self._hass.states.get(self._tariff_sensor_id).state)

        self._charge_state = float(self._charge_state) + amount_to_charge - amount_to_discharge

        self._sensors[ATTR_ENERGY_SAVED] += amount_to_discharge
        self._sensors[GRID_IMPORT_SIM] += net_import
        self._sensors[GRID_EXPORT_SIM] += net_export
        self._sensors[ATTR_ENERGY_BATTERY_IN] += amount_to_charge
        self._sensors[ATTR_ENERGY_BATTERY_OUT] += amount_to_discharge
        self._sensors[CHARGING_RATE] = amount_to_charge/(time_since_last_battery_update/3600)
        self._sensors[DISCHARGING_RATE] = amount_to_discharge/(time_since_last_battery_update/3600)

        self._charge_percentage = round(100*self._charge_state/self._battery_size)
        if self._tariff_sensor_id != "none":
            self._sensors[ATTR_MONEY_SAVED] += net_money_saved
        self._energy_saved_today += amount_to_discharge
        self._energy_saved_week += amount_to_discharge
        self._energy_saved_month += amount_to_discharge

        """Reset day/week/month counters"""
        if time.strftime("%w") != time.strftime("%w", time.gmtime(self._last_battery_update_time)):
            self._energy_saved_today = 0
        if time.strftime("%U") != time.strftime("%U", time.gmtime(self._last_battery_update_time)):
            self._energy_saved_week = 0
        if time.strftime("%m") != time.strftime("%m", time.gmtime(self._last_battery_update_time)):
            self._energy_saved_month = 0

        self._last_battery_update_time = time_now
        dispatcher_send(self._hass, f"{self._name}-BatteryUpdateMessage")
        _LOGGER.debug("Battery update complete (%s). Sensors: %s", self._name, self._sensors)
