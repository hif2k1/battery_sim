"""Utility meter from sensors providing raw data."""
import time
from decimal import Decimal, DecimalException
import logging

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    CONF_NAME,
    DEVICE_CLASS_ENERGY,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (
    async_track_state_change_event
)
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_BATTERY,
    CONF_BATTERY_EFFICIENCY,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_SIZE,
    CONF_IMPORT_SENSOR,
    CONF_EXPORT_SENSOR,
    CONF_ENERGY_TARIFF,
    ATTR_MONEY_SAVED,
    DATA_UTILITY,
    ATTR_SOURCE_ID,
    ATTR_CHARGING_RATE,
    ATTR_DISCHARGING_RATE,
    ATTR_STATUS,
    ATTR_ENERGY_SAVED,
    ATTR_ENERGY_SAVED_TODAY,
    ATTR_ENERGY_SAVED_WEEK,
    ATTR_ENERGY_SAVED_MONTH,
    ATTR_DATE_RECORDING_STARTED,
    CHARGING,
    DISCHARGING,
    ATTR_CHARGE_PERCENTAGE
)

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAP = {
    ENERGY_WATT_HOUR: DEVICE_CLASS_ENERGY,
    ENERGY_KILO_WATT_HOUR: DEVICE_CLASS_ENERGY,
}

ICON_CHARGING = "mdi:battery-charging-50"
ICON_DISCHARGING = "mdi:battery-50"
ATTR_MAX_DISCHARGE = "max possible discharge since last update"

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the utility meter sensor."""
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    batteries = []
    for conf in discovery_info:
        battery = conf[CONF_BATTERY]
        conf_import_sensor = hass.data[DATA_UTILITY][battery][CONF_IMPORT_SENSOR]
        conf_export_sensor = hass.data[DATA_UTILITY][battery][CONF_EXPORT_SENSOR]
        if CONF_ENERGY_TARIFF in hass.data[DATA_UTILITY][battery]:
            conf_tariff_sensor = hass.data[DATA_UTILITY][battery][CONF_ENERGY_TARIFF]
        else:
            conf_tariff_sensor = "none"
        conf_battery_size = hass.data[DATA_UTILITY][battery].get(CONF_BATTERY_SIZE)
        conf_battery_efficiency = hass.data[DATA_UTILITY][battery].get(CONF_BATTERY_EFFICIENCY)
        conf_battery_max_discharge_rate = hass.data[DATA_UTILITY][battery].get(CONF_BATTERY_MAX_DISCHARGE_RATE)
        conf_battery_max_charge_rate = hass.data[DATA_UTILITY][battery].get(CONF_BATTERY_MAX_CHARGE_RATE)

        batteries.append(
            SimulatedBattery(
                conf_import_sensor,
                conf_export_sensor,
                conf_tariff_sensor,
                conf_battery_size,
                conf_battery_max_discharge_rate,
                conf_battery_max_charge_rate,
                conf_battery_efficiency,
                conf.get(CONF_NAME)
            )
        )

    async_add_entities(batteries)

class SimulatedBattery(RestoreEntity, SensorEntity):
    """Representation of a battery."""

    def __init__(
        self,
        import_sensor,
        export_sensor,
        tariff_sensor,
        battery_size,
        max_discharge_rate,
        max_charge_rate,
        battery_efficiency,
        name,
    ):
        """Initialize the Battery."""
        self._import_sensor_id = import_sensor
        self._export_sensor_id = export_sensor
        self._tariff_sensor_id = tariff_sensor
        self._state = 0
        self._energy_saved = 0
        self._money_saved = 0
        self._energy_saved_today = 0
        self._energy_saved_week = 0
        self._energy_saved_month = 0
        self._date_recording_started = time.asctime()
        self._collecting1 = None
        self._collecting2 = None
        self._charging = False
        if name:
            self._name = name
        else:
            self._name = f"{battery_size} kwh battery"
        self._battery_size = battery_size
        self._max_discharge_rate = max_discharge_rate
        self._max_charge_rate = max_charge_rate
        self._battery_efficiency = battery_efficiency
        self._last_import_reading_time = time.time()
        self._last_export_reading_time = time.time()
        self._max_discharge = 0
        self._charge_percentage = 0
        self._charging_rate = 0
        self._discharging_rate = 0

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

        if self._state=='unknown': self._state = 0

        try:
            """Calculate maximum possible charge based on battery specifications"""
            time_now = time.time()
            time_since_last_export = time_now-self._last_export_reading_time
            self._last_export_reading_time = time_now
            max_charge = time_since_last_export*self._max_charge_rate/3600

            diff = float(new_state.state) - float(old_state.state)

            if diff <= 0:
                self._charging_rate = 0
                return
            
            available_capacity = self._battery_size - float(self._state)

            diff = min(diff, max_charge, available_capacity)

            self._state = float(self._state) + diff
            self._charging = True
            self._charge_percentage = round(100*float(self._state)/float(self._battery_size))
            self._charging_rate = diff/(time_since_last_export/3600)

        except ValueError as err:
            _LOGGER.warning("While processing state changes: %s", err)
        except DecimalException as err:
            _LOGGER.warning(
                "Invalid state (%s > %s): %s", old_state.state, new_state.state, err
            )
        self.schedule_update_ha_state(True)

    @callback
    def async_import_reading(self, event):
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

        if self._state=='unknown': self._state = 0

        try:
            """Calculate maximum possible discharge based on battery specifications"""
            time_now = time.time()

            if time.strftime("%w") != time.strftime("%w", time.gmtime(self._last_import_reading_time)):
                self._energy_saved_today = 0
            if time.strftime("%U") != time.strftime("%U", time.gmtime(self._last_import_reading_time)):
                self._energy_saved_week = 0
            if time.strftime("%m") != time.strftime("%m", time.gmtime(self._last_import_reading_time)):
                self._energy_saved_month = 0
 
            time_since_last_import = time_now-self._last_import_reading_time
            self._last_import_reading_time = time_now
            max_discharge = time_since_last_import*self._max_discharge_rate/3600

            diff = float(new_state.state) - float(old_state.state)
            if diff <= 0:
                self._discharging_rate = 0
                return

            diff = min(diff, max_discharge, float(self._state)*float(self._battery_efficiency))

            self._state = float(self._state) - diff/float(self._battery_efficiency)
            self._energy_saved += diff
            self._energy_saved_today += diff
            self._energy_saved_week += diff
            self._energy_saved_month += diff
            self._charge_percentage = round(100*float(self._state)/float(self._battery_size))
            
            if self._tariff_sensor_id != "none":
                self._money_saved += diff*float(self.hass.states.get(self._tariff_sensor_id).state)

            self._charging = False
            self._discharging_rate = diff/(time_since_last_import/3600)

        except ValueError as err:
            _LOGGER.warning("While processing state changes: %s", err)
        except DecimalException as err:
            _LOGGER.warning(
                "Invalid state (%s > %s): %s", old_state.state, new_state.state, err
            )
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state:
            self._state = state.state
            if ATTR_ENERGY_SAVED in state.attributes:
                self._energy_saved = state.attributes[ATTR_ENERGY_SAVED]
            if ATTR_DATE_RECORDING_STARTED in state.attributes:
                self._date_recording_started = state.attributes[ATTR_DATE_RECORDING_STARTED]
            if ATTR_ENERGY_SAVED_TODAY in state.attributes:
                self._energy_saved_today = state.attributes[ATTR_ENERGY_SAVED_TODAY]
            if ATTR_ENERGY_SAVED_WEEK in state.attributes:
                self._energy_saved_week = state.attributes[ATTR_ENERGY_SAVED_WEEK]
            if ATTR_ENERGY_SAVED_MONTH in state.attributes:
                self._energy_saved_month = state.attributes[ATTR_ENERGY_SAVED_MONTH]
            if self._tariff_sensor_id != "none" and ATTR_MONEY_SAVED in state.attributes:
               self._money_saved = state.attributes[ATTR_MONEY_SAVED]
            
        @callback
        def async_source_tracking(event):
            """Wait for source to be ready, then start."""
 
            _LOGGER.debug("<%s> collecting from %s", self.name, self._import_sensor_id)
            self._collecting1 = async_track_state_change_event(
                self.hass, [self._import_sensor_id], self.async_import_reading
            )
            _LOGGER.debug("<%s> collecting from %s", self.name, self._export_sensor_id)
            self._collecting2 = async_track_state_change_event(
                self.hass, [self._export_sensor_id], self.async_export_reading
            )

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, async_source_tracking
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return round(float(self._state),2)

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_ENERGY

    @property
    def state_class(self):
        """Return the device class of the sensor."""
        return (
            STATE_CLASS_MEASUREMENT
        )

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return ENERGY_KILO_WATT_HOUR

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return ENERGY_KILO_WATT_HOUR

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {
            ATTR_SOURCE_ID: self._export_sensor_id,
            ATTR_STATUS: CHARGING if self._charging else DISCHARGING,
            ATTR_CHARGING_RATE: round(self._charging_rate,2),
            ATTR_DISCHARGING_RATE: round(self._discharging_rate,2),
            ATTR_CHARGE_PERCENTAGE: int(self._charge_percentage),
            ATTR_DATE_RECORDING_STARTED: self._date_recording_started,
            ATTR_ENERGY_SAVED: round(float(self._energy_saved),2),
            ATTR_MONEY_SAVED: round(float(self._money_saved),2),
            ATTR_ENERGY_SAVED_TODAY: round(float(self._energy_saved_today),2),
            ATTR_ENERGY_SAVED_WEEK: round(float(self._energy_saved_week),2),
            ATTR_ENERGY_SAVED_MONTH: round(float(self._energy_saved_month),2),
            CONF_BATTERY_SIZE: self._battery_size,
            CONF_BATTERY_EFFICIENCY: float(self._battery_efficiency),
            CONF_BATTERY_MAX_DISCHARGE_RATE: float(self._max_discharge_rate),
            CONF_BATTERY_MAX_CHARGE_RATE: float(self._max_charge_rate)
        }
        return state_attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if self._charging:
            return ICON_CHARGING
        else:
            return ICON_DISCHARGING

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(float(self._state),2)

    def update(self):
        """Not used"""
