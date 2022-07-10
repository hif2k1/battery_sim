"""Simulated battery and associated sensors"""
import time
import logging

import homeassistant.util.dt as dt_util
from homeassistant.helpers.dispatcher import dispatcher_send, async_dispatcher_connect
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL,
    SensorEntity,
)
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
    DEVICE_CLASS_MONETARY,
    ENERGY_WATT_HOUR,
    ENERGY_KILO_WATT_HOUR
)
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    CONF_BATTERY,
    CONF_BATTERY_EFFICIENCY,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_SIZE,
    ATTR_MONEY_SAVED,
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
    ICON_DISCHARGING,
    PERCENTAGE_ENERGY_IMPORT_SAVED
)

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAP = {
    ENERGY_WATT_HOUR: DEVICE_CLASS_ENERGY,
    ENERGY_KILO_WATT_HOUR: DEVICE_CLASS_ENERGY,
}

async def async_setup_entry(hass, config_entry, async_add_entities):
    handle = hass.data[DOMAIN][config_entry.entry_id]
    sensors = await define_sensors(hass, handle)
    async_add_entities(sensors)

async def async_setup_platform(hass, configuration, async_add_entities, discovery_info=None):
    if discovery_info is None:
        return

    for conf in discovery_info:
        battery = conf[CONF_BATTERY]
        handle = hass.data[DOMAIN][battery]
        sensors = await define_sensors(hass, handle)
        async_add_entities(sensors)

async def define_sensors(hass, handle):
    sensors = []
    sensors.append(DisplayOnlySensor(handle, ATTR_ENERGY_SAVED, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR))
    sensors.append(DisplayOnlySensor(handle, ATTR_ENERGY_BATTERY_OUT, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR))
    sensors.append(DisplayOnlySensor(handle, ATTR_ENERGY_BATTERY_IN, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR))
    sensors.append(DisplayOnlySensor(handle, CHARGING_RATE, DEVICE_CLASS_POWER, POWER_KILO_WATT))
    sensors.append(DisplayOnlySensor(handle, DISCHARGING_RATE, DEVICE_CLASS_POWER, POWER_KILO_WATT))
    sensors.append(DisplayOnlySensor(handle, GRID_EXPORT_SIM, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR))
    sensors.append(DisplayOnlySensor(handle, GRID_IMPORT_SIM, DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR))
    if handle._tariff_sensor_id != "none":
        sensors.append(DisplayOnlySensor(handle, ATTR_MONEY_SAVED, DEVICE_CLASS_MONETARY, hass.config.currency))
    sensors.append(SimulatedBattery(handle))
    return sensors

class DisplayOnlySensor(RestoreEntity, SensorEntity):
    """Representation of a sensor which simply displays a value calculated in another sensor"""
    def __init__(
        self,
        handle,
        sensor_name,
        type_of_sensor,
        units
    ):
        self._handle = handle
        self._units = units
        self._name = handle._name + " - " + sensor_name
        self._device_name = handle._name
        self._sensor_type = sensor_name
        self._type_of_sensor = type_of_sensor
        self._last_reset = dt_util.utcnow()

    async def async_added_to_hass(self):
        """Subscribe for update from the battery."""

        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state:
            self._handle._sensors[self._sensor_type] = float(state.state)
        else:
            if self._sensor_type == GRID_IMPORT_SIM:
                dispatcher_send(self.hass, f"{self._name}-BatteryResetImportSim")
            elif self._sensor_type == GRID_EXPORT_SIM:
                dispatcher_send(self.hass, f"{self._name}-BatteryResetExportSim")

        async def async_update_state():
            """Update sensor state."""
            await self.async_update_ha_state(True)

        async_dispatcher_connect(
            self.hass, f"{self._handle._name}-BatteryUpdateMessage", async_update_state
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
                "name": self._device_name,
                "identifiers": {
                    (DOMAIN, self._device_name)
                }
            }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return round(float(self._handle._sensors[self._sensor_type]),2)

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
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {}
        if(self._sensor_type == ATTR_ENERGY_SAVED):
            state_attr = {
                ATTR_ENERGY_SAVED_TODAY: round(float(self._handle._energy_saved_today),2),
                ATTR_ENERGY_SAVED_WEEK: round(float(self._handle._energy_saved_week),2),
                ATTR_ENERGY_SAVED_MONTH: round(float(self._handle._energy_saved_month),2)
            }
        elif(self._sensor_type == GRID_IMPORT_SIM):
            real_world_import = self._handle._last_import_cumulative_reading
            simulated_import = self._handle._sensors[GRID_IMPORT_SIM]
            if real_world_import==0:
                _LOGGER.warning("Division by zero, real world: %s, simulated: %s, battery: %s", real_world_import, simulated_import, self._name)
                state_attr = {
                    PERCENTAGE_ENERGY_IMPORT_SAVED: 0
                }
            else:
                percentage_import_saved = 100*(real_world_import-simulated_import)/real_world_import
                state_attr = {
                    PERCENTAGE_ENERGY_IMPORT_SAVED: round(float(percentage_import_saved),0)
                }
        return state_attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(float(self._handle._sensors[self._sensor_type]),2)

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
        handle
    ):
        self.handle = handle
        self._date_recording_started = time.asctime()
        self._name = handle._name

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state:
            self.handle._charge_state = float(state.state)
            if ATTR_DATE_RECORDING_STARTED in state.attributes:
                self.handle._date_recording_started = state.attributes[ATTR_DATE_RECORDING_STARTED]
            if ATTR_ENERGY_SAVED_TODAY in state.attributes:
                self._energy_saved_today = state.attributes[ATTR_ENERGY_SAVED_TODAY]
            if ATTR_ENERGY_SAVED_WEEK in state.attributes:
                self._energy_saved_week = state.attributes[ATTR_ENERGY_SAVED_WEEK]
            if ATTR_ENERGY_SAVED_MONTH in state.attributes:
                self._energy_saved_month = state.attributes[ATTR_ENERGY_SAVED_MONTH]

        async def async_update_state():
            """Update sensor state."""
            await self.async_update_ha_state(True)

        async_dispatcher_connect(
            self.hass, f"{self.handle._name}-BatteryUpdateMessage", async_update_state
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.handle._name

    @property
    def unique_id(self):
        """Return uniqueid."""
        return self.handle._name
 
    @property
    def device_info(self):
        return {
                "name": self.handle._name,
                "identifiers": {
                    (DOMAIN, self.handle._name)
                },
            }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return round(float(self.handle._charge_state),2)

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
            ATTR_STATUS: CHARGING if self.handle._charging else DISCHARGING,
            ATTR_CHARGE_PERCENTAGE: int(self.handle._charge_percentage),
            ATTR_DATE_RECORDING_STARTED: self.handle._date_recording_started,
            ATTR_ENERGY_SAVED_TODAY: round(float(self.handle._energy_saved_today),2),
            ATTR_ENERGY_SAVED_WEEK: round(float(self.handle._energy_saved_week),2),
            ATTR_ENERGY_SAVED_MONTH: round(float(self.handle._energy_saved_month),2),
            CONF_BATTERY_SIZE: self.handle._battery_size,
            CONF_BATTERY_EFFICIENCY: float(self.handle._battery_efficiency),
            CONF_BATTERY_MAX_DISCHARGE_RATE: float(self.handle._max_discharge_rate),
            CONF_BATTERY_MAX_CHARGE_RATE: float(self.handle._max_charge_rate),
            ATTR_SOURCE_ID: self.handle._export_sensor_id
        }
        return state_attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if self.handle._charging:
            return ICON_CHARGING
        else:
            return ICON_DISCHARGING

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(float(self.handle._charge_state),2)

    def update(self):
        """Not used"""