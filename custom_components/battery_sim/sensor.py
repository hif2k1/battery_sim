"""Simulated battery and associated sensors"""
import time
import logging

import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    CONF_NAME,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_WATT_HOUR,
    ENERGY_KILO_WATT_HOUR,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
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
    ATTR_STATUS,
    ATTR_ENERGY_SAVED,
    ATTR_ENERGY_SAVED_TODAY,
    ATTR_ENERGY_SAVED_WEEK,
    ATTR_ENERGY_SAVED_MONTH,
    ATTR_DATE_RECORDING_STARTED,
    CHARGING,
    DISCHARGING,
    ATTR_CHARGE_PERCENTAGE,
    ATTR_ENERGY_BATTERY_OUT,
    ATTR_ENERGY_BATTERY_IN,
    CHARGING_RATE,
    DISCHARGING_RATE,
    GRID_IMPORT_SIM,
    GRID_EXPORT_SIM,
    ICON_CHARGING,
    ICON_DISCHARGING
)

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAP = {
    ENERGY_WATT_HOUR: DEVICE_CLASS_ENERGY,
    ENERGY_KILO_WATT_HOUR: DEVICE_CLASS_ENERGY,
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = hass.data[DOMAIN][config_entry.entry_id]
    sensors = await define_sensors(hass, config)
    async_add_entities(sensors)

async def async_setup_platform(hass, configuration, async_add_entities, discovery_info=None):
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    for conf in discovery_info:
        battery = conf[CONF_BATTERY]
        config = hass.data[DATA_UTILITY][battery]
        sensors = await define_sensors(hass, config)
        async_add_entities(sensors)

async def define_sensors(hass, config):
    if CONF_ENERGY_TARIFF not in config:
        conf_tarrif = "none"
    else:
        conf_tarrif = config[CONF_ENERGY_TARIFF]
    import_sensor = hass.states.get(config[CONF_IMPORT_SENSOR])
    export_sensor = hass.states.get(config[CONF_EXPORT_SENSOR])

    sensors = []
    energySavedSensor = DisplayOnlySensor(config[CONF_NAME], ATTR_ENERGY_SAVED, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR)
    energyBatteryOutSensor = DisplayOnlySensor(config[CONF_NAME], ATTR_ENERGY_BATTERY_OUT, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR)
    energyBatteryInSensor = DisplayOnlySensor(config[CONF_NAME], ATTR_ENERGY_BATTERY_IN, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR)
    chargingRateSensor = DisplayOnlySensor(config[CONF_NAME], CHARGING_RATE, DEVICE_CLASS_POWER, POWER_KILO_WATT)
    dischargingRateSensor = DisplayOnlySensor(config[CONF_NAME], DISCHARGING_RATE, DEVICE_CLASS_POWER, POWER_KILO_WATT)
    simulatedExportSensor = DisplayOnlySensor(config[CONF_NAME], GRID_EXPORT_SIM, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR, export_sensor)
    simulatedImportSensor = DisplayOnlySensor(config[CONF_NAME], GRID_IMPORT_SIM, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR, import_sensor)
    sensors.append(energySavedSensor)
    sensors.append(energyBatteryOutSensor)
    sensors.append(energyBatteryInSensor)
    sensors.append(chargingRateSensor)
    sensors.append(dischargingRateSensor)
    sensors.append(simulatedExportSensor)
    sensors.append(simulatedImportSensor)
    sensors.append(
        SimulatedBattery(
            config[CONF_IMPORT_SENSOR],
            config[CONF_EXPORT_SENSOR],
            conf_tarrif,
            config[CONF_BATTERY_SIZE],
            config[CONF_BATTERY_MAX_DISCHARGE_RATE],
            config[CONF_BATTERY_MAX_CHARGE_RATE],
            config[CONF_BATTERY_EFFICIENCY],
            config[CONF_NAME],
            energySavedSensor,
            energyBatteryOutSensor,
            energyBatteryInSensor,
            chargingRateSensor,
            dischargingRateSensor,
            simulatedImportSensor,
            simulatedExportSensor
        )
    )
    return sensors

class DisplayOnlySensor(RestoreEntity, SensorEntity):
    """Representation of a sensor which simply displays a value calculated in another sensor"""
    def __init__(
        self,
        device_name,
        sensor_name,
        type_of_sensor,
        units,
        comparitor_sensor=None
    ):
        self._units = units
        self._name = device_name + " - " + sensor_name
        self._device_name = device_name
        self._type_of_sensor = type_of_sensor
        self._last_reset = dt_util.utcnow()
        if comparitor_sensor is not None:
            self._comparitor_sensor = comparitor_sensor
            self._state = float(self._comparitor_sensor.state)
        else:
            self._state = 0.0

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state:
            self._state = float(state.state)

    @callback
    def update_value(self, value):
        self._state = value
        self.schedule_update_ha_state(True)
        self._last_reset = dt_util.utcnow()
    
    @callback
    def increment_value(self, value):
        self._state += float(value)
        self.schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return uniqueid."""
        return self._name

    @property
    def device_info(self):
        return {
                "name": self._device_name,
                "identifiers": {
                    (DOMAIN, self._device_name)
                },
            }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return round(float(self._state),2)

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._type_of_sensor

    @property
    def state_class(self):
        """Return the device class of the sensor."""
        return (
            STATE_CLASS_TOTAL
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

    @property
    def last_reset(self):
        """Return the time when the sensor was last reset."""
        return self._last_reset

class SimulatedBattery(RestoreEntity, SensorEntity):
    """Representation of the battery itself"""

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
        self._state = 0.0
        self._energy_saved = 0.0
        self._money_saved = 0.0
        self._energy_saved_today = 0.0
        self._energy_saved_week = 0.0
        self._energy_saved_month = 0.0
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
        self._max_discharge = 0.0
        self._charge_percentage = 0.0
        self._energy_battery_in_sensor = energyBatteryInSensor
        self._energy_battery_out_sensor = energyBatteryOutSensor
        self._energy_saved_sensor = energySavedSensor
        self._charging_rate_sensor = chargingRateSensor
        self._discharging_rate_sensor = dischargingRateSensor
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

        if self._state=='unknown': self._state = 0.0 

        """Calculate maximum possible charge based on battery specifications"""
        time_now = time.time()
        time_since_last_export = time_now-self._last_export_reading_time
        self._last_export_reading_time = time_now
        max_charge = time_since_last_export*self._max_charge_rate/3600
        
        conversion_factor = 1.0
        units = self.hass.states.get(self._export_sensor_id).attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if units == ENERGY_WATT_HOUR:
            conversion_factor = 0.001
        elif units == ENERGY_KILO_WATT_HOUR:
            conversion_factor = 1
        else:
            _LOGGER.warning("Units of import sensor not recognised - may give wrong results")

        diff = conversion_factor*(float(new_state.state) - float(old_state.state))

        """Check for sensor reset"""
        if float(self._simulated_grid_export_sensor.state) > float(old_state.state):
            self._simulated_grid_export_sensor.update_value(float(old_state.state))
        if diff <= 0:
            self._charging_rate_sensor.update_value(0)
            return

        """fix bug where if there is no change in import reading then discharging doesn't update"""
        self._discharging_rate_sensor.update_value(0)
        
        available_capacity = self._battery_size - float(self._state)

        amount_to_charge = min(diff, max_charge, available_capacity)

        self._state = float(self._state) + amount_to_charge
        self._simulated_grid_export_sensor.increment_value(diff - amount_to_charge)
        self._charging = True
        self._charge_percentage = round(100*float(self._state)/float(self._battery_size))
        self._charging_rate_sensor.update_value(
            amount_to_charge/(time_since_last_export/3600)
            )
        self._energy_battery_in_sensor.increment_value(amount_to_charge)

        self.schedule_update_ha_state(True)

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

        if self._state=='unknown': self._state = 0.0

        """Reset day/week/month counters"""
        if time.strftime("%w") != time.strftime("%w", time.gmtime(self._last_import_reading_time)):
            self._energy_saved_today = 0
        if time.strftime("%U") != time.strftime("%U", time.gmtime(self._last_import_reading_time)):
            self._energy_saved_week = 0
        if time.strftime("%m") != time.strftime("%m", time.gmtime(self._last_import_reading_time)):
            self._energy_saved_month = 0

        """Calculate maximum possible discharge based on battery specifications and time since last discharge"""
        time_now = time.time()
        time_since_last_import = time_now-self._last_import_reading_time
        self._last_import_reading_time = time_now
        max_discharge = time_since_last_import*self._max_discharge_rate/3600

        """Check units of import sensor and calculate import amount in kWh"""
        conversion_factor = 1.0
        units = self.hass.states.get(self._import_sensor_id).attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if units == ENERGY_WATT_HOUR:
            conversion_factor = 0.001
        elif units == ENERGY_KILO_WATT_HOUR:
            conversion_factor = 1
        else:
            _LOGGER.warning("Units of import sensor not recognised - may give wrong results")
        diff = conversion_factor*(float(new_state.state) - float(old_state.state))

        """Check for sensor reset"""
        if float(self._simulated_grid_import_sensor.state) > float(old_state.state):
            self._simulated_grid_import_sensor.update_value(float(old_state.state))
        if diff <= 0:
            self._discharging_rate_sensor.update_value(0)
            return

        """fix bug where if there is no change in export reading then charging doesn't update"""
        self._charging_rate_sensor.update_value(0)

        amount_to_discharge = min(diff, max_discharge, float(self._state)*float(self._battery_efficiency))

        self._state = float(self._state) - amount_to_discharge/float(self._battery_efficiency)
        self._energy_saved_sensor.increment_value(amount_to_discharge)
        self._energy_battery_out_sensor.increment_value(amount_to_discharge)
        self._energy_saved_today += amount_to_discharge
        self._energy_saved_week += amount_to_discharge
        self._energy_saved_month += amount_to_discharge
        self._charge_percentage = round(100*self._state/self._battery_size)
        
        self._simulated_grid_import_sensor.increment_value(
            diff - amount_to_discharge
            )

        if self._tariff_sensor_id != "none":
            self._money_saved += amount_to_discharge*float(self.hass.states.get(self._tariff_sensor_id).state)

        self._charging = False
        self._discharging_rate_sensor.update_value(
            amount_to_discharge/(time_since_last_import/3600)
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
    def unique_id(self):
        """Return uniqueid."""
        return self._name
 
    @property
    def device_info(self):
        return {
                "name": self._name,
                "identifiers": {
                    (DOMAIN, self.name)
                },
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
            ATTR_CHARGE_PERCENTAGE: int(self._charge_percentage),
            ATTR_DATE_RECORDING_STARTED: self._date_recording_started,
            ATTR_MONEY_SAVED: round(float(self._money_saved),2),
            ATTR_ENERGY_SAVED_TODAY: round(float(self._energy_saved_today),2),
            ATTR_ENERGY_SAVED_WEEK: round(float(self._energy_saved_week),2),
            ATTR_ENERGY_SAVED_MONTH: round(float(self._energy_saved_month),2),
            CONF_BATTERY_SIZE: self._battery_size,
            CONF_BATTERY_EFFICIENCY: float(self._battery_efficiency),
            CONF_BATTERY_MAX_DISCHARGE_RATE: float(self._max_discharge_rate),
            CONF_BATTERY_MAX_CHARGE_RATE: float(self._max_charge_rate),
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
