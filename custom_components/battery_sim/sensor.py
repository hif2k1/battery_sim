"""Utility meter from sensors providing raw data."""
import time
from decimal import Decimal, DecimalException
import logging

from homeassistant.components.sensor import (
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    CONF_NAME,
    DEVICE_CLASS_ENERGY,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
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
    ATTR_ENERGY_BATTERY_OUT,
    ATTR_ENERGY_BATTERY_IN,
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

        if conf.get(CONF_NAME):
            conf_name = conf.get(CONF_NAME)
        else:
            conf_name = f"{conf_battery_size} kwh battery"

        energySavedSensor = DisplayOnlySensor(conf_name + " - total energy saved", ENERGY_KILO_WATT_HOUR)
        energyBatteryOutSensor = DisplayOnlySensor(conf_name + " - batery energy out", ENERGY_KILO_WATT_HOUR)
        energyBatteryInSensor = DisplayOnlySensor(conf_name + " - battery energy in", ENERGY_KILO_WATT_HOUR)
        chargingRateSensor = DisplayOnlySensor(conf_name + " - current charging rate", POWER_KILO_WATT)
        dischargingRateSensor = DisplayOnlySensor(conf_name + " - current discharging rate", POWER_KILO_WATT)
        simulatedExportSensor = DisplayOnlySensor(conf_name + " - simulated grid export after battery charging", ENERGY_KILO_WATT_HOUR)
        simulatedImportSensor = DisplayOnlySensor(conf_name + " - simulated grid import after battery discharging", ENERGY_KILO_WATT_HOUR)
        batteries.append(energySavedSensor)
        batteries.append(energyBatteryOutSensor)
        batteries.append(energyBatteryInSensor)
        batteries.append(chargingRateSensor)
        batteries.append(dischargingRateSensor)
        batteries.append(simulatedExportSensor)
        batteries.append(simulatedImportSensor)
        batteries.append(
            SimulatedBattery(
                conf_import_sensor,
                conf_export_sensor,
                conf_tariff_sensor,
                conf_battery_size,
                conf_battery_max_discharge_rate,
                conf_battery_max_charge_rate,
                conf_battery_efficiency,
                conf_name,
                energySavedSensor,
                energyBatteryOutSensor,
                energyBatteryInSensor,
                chargingRateSensor,
                dischargingRateSensor,
                simulatedImportSensor,
                simulatedExportSensor
            )
        )
    async_add_entities(batteries)

class DisplayOnlySensor(SensorEntity):
    """Representation of a sensor which simply displays a value calculated in another sensor"""
    def __init__(
        self,
        name,
        units,
    ):
        self._units = units
        self._name = name
        self._state = 0.0

    @callback
    def update_value(self, value):
        self._state = value
        self.schedule_update_ha_state(True)

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
            STATE_CLASS_TOTAL_INCREASING
        )

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._units

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(float(self._state),2)

    def update(self):
        """Not used"""

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
        energySavedSensor,
        energyBatteryOutSensor,
        energyBatteryInSensor,
        chargingRateSensor,
        dischargingRateSensor,
        simulatedImportSensor,
        simulatedExportSensor
    ):
        """Initialize the Battery."""
        self._import_sensor_id = import_sensor
        self._export_sensor_id = export_sensor
        self._tariff_sensor_id = tariff_sensor
        self._state = 0
        self._energy_saved = 0
        self._energy_battery_out = 0
        self._energy_battery_in = 0
        self._money_saved = 0
        self._energy_saved_today = 0
        self._energy_saved_week = 0
        self._energy_saved_month = 0
        self._date_recording_started = time.asctime()
        self._collecting1 = None
        self._collecting2 = None
        self._charging = False
        self._name = name
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
        self._energy_saved_sensor = energySavedSensor
        self._energy_battery_out_sensor = energyBatteryOutSensor
        self._energy_battery_in_sensor = energyBatteryInSensor
        self._charging_rate_sensor = chargingRateSensor
        self._discharging_rate_sensor = dischargingRateSensor
        self._simulated_grid_import = 0
        self._simulated_grid_export = 0
        self._simulated_grid_import_sensor = simulatedImportSensor
        self._simulated_grid_export_sensor = simulatedExportSensor

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
        if (self._simulated_grid_export == 0):
            self._simulated_grid_export = float(old_state.state)    

        try:
            """Calculate maximum possible charge based on battery specifications"""
            time_now = time.time()
            time_since_last_export = time_now-self._last_export_reading_time
            self._last_export_reading_time = time_now
            max_charge = time_since_last_export*self._max_charge_rate/3600

            diff = float(new_state.state) - float(old_state.state)

            if self._simulated_grid_export > float(old_state.state):
                self._simulated_grid_export = float(old_state.state)
                self._simulated_grid_export_sensor.update_value(self._simulated_grid_export)
            if diff <= 0:
                self._charging_rate = 0
                self._charging_rate_sensor.update_value(0)
                return

            """fix bug where if there is no change in import reading then discharging doesn't update"""
            self._discharging_rate_sensor.update_value(0)
            
            available_capacity = self._battery_size - float(self._state)

            amount_to_charge = min(diff, max_charge, available_capacity)

            self._state = float(self._state) + amount_to_charge
            self._energy_battery_in += amount_to_charge
            self._energy_battery_in_sensor.update_value(self._energy_battery_in)
            self._simulated_grid_export += diff - amount_to_charge
            self._simulated_grid_export_sensor.update_value(self._simulated_grid_export)
            self._charging = True
            self._charge_percentage = round(100*float(self._state)/float(self._battery_size))
            self._charging_rate = amount_to_charge/(time_since_last_export/3600)
            self._charging_rate_sensor.update_value(self._charging_rate)

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

        if (self._simulated_grid_import == 0):
            self._simulated_grid_import = float(old_state.state)

        if self._state=='unknown': self._state = 0.0

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
            if self._simulated_grid_import > float(old_state.state):
                self._simulated_grid_import = float(old_state.state)
                self._simulated_grid_import_sensor.update_value(self._simulated_grid_import)
            if diff <= 0:
                self._discharging_rate = 0
                self._discharging_rate_sensor.update_value(0)
                return

            """fix bug where if there is no change in import reading then discharging doesn't update"""
            self._charging_rate_sensor.update_value(0)

            amount_to_discharge = min(diff, max_discharge, float(self._state)*float(self._battery_efficiency))

            self._state = float(self._state) - amount_to_discharge/float(self._battery_efficiency)
            self._energy_saved += amount_to_discharge
            self._energy_saved_sensor.update_value(self._energy_saved)
            self._energy_battery_out += amount_to_discharge
            self._energy_battery_out_sensor.update_value(self._energy_battery_out)            
            self._energy_saved_today += amount_to_discharge
            self._energy_saved_week += amount_to_discharge
            self._energy_saved_month += amount_to_discharge
            self._charge_percentage = round(100*self._state/self._battery_size)
            
            self._simulated_grid_import += diff - amount_to_discharge
            self._simulated_grid_import_sensor.update_value(self._simulated_grid_import)

            if self._tariff_sensor_id != "none":
                self._money_saved += amount_to_discharge*float(self.hass.states.get(self._tariff_sensor_id).state)

            self._charging = False
            self._discharging_rate = amount_to_discharge/(time_since_last_import/3600)
            self._discharging_rate_sensor.update_value(self._discharging_rate)

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
            if ATTR_ENERGY_BATTERY_OUT in state.attributes:
                self._energy_battery_out = state.attributes[ATTR_ENERGY_BATTERY_OUT]
            if ATTR_ENERGY_BATTERY_IN in state.attributes:
                self._energy_battery_in = state.attributes[ATTR_ENERGY_BATTERY_IN]
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
    def device_info(self):
        return {
            "identifiers": {
                ("batteries", 123456)
            },
            "name": self.name,
        }

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
            STATE_CLASS_TOTAL_INCREASING
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
            ATTR_ENERGY_BATTERY_OUT: round(float(self._energy_battery_out),2),
            ATTR_ENERGY_BATTERY_IN: round(float(self._energy_battery_in),2),
            ATTR_MONEY_SAVED: round(float(self._money_saved),2),
            ATTR_ENERGY_SAVED_TODAY: round(float(self._energy_saved_today),2),
            ATTR_ENERGY_SAVED_WEEK: round(float(self._energy_saved_week),2),
            ATTR_ENERGY_SAVED_MONTH: round(float(self._energy_saved_month),2),
            CONF_BATTERY_SIZE: self._battery_size,
            CONF_BATTERY_EFFICIENCY: float(self._battery_efficiency),
            CONF_BATTERY_MAX_DISCHARGE_RATE: float(self._max_discharge_rate),
            CONF_BATTERY_MAX_CHARGE_RATE: float(self._max_charge_rate),
            "Simulated import": self._simulated_grid_import,
            "Simulated export": self._simulated_grid_export
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
