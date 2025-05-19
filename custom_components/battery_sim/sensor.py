"""Simulated battery and associated sensors."""
import time
import logging

import homeassistant.util.dt as dt_util
from homeassistant.helpers.dispatcher import dispatcher_send, async_dispatcher_connect

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    ATTR_LAST_RESET,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPower,
    UnitOfEnergy,
)

from .const import (
    DOMAIN,
    CONF_BATTERY,
    CONF_BATTERY_EFFICIENCY,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_SIZE,
    ATTR_MONEY_SAVED,
    ATTR_MONEY_SAVED_IMPORT,
    ATTR_MONEY_SAVED_EXPORT,
    ATTR_SOURCE_ID,
    ATTR_STATUS,
    ATTR_ENERGY_SAVED,
    ATTR_DATE_RECORDING_STARTED,
    BATTERY_MODE,
    ATTR_CHARGE_PERCENTAGE,
    ATTR_ENERGY_BATTERY_OUT,
    ATTR_ENERGY_BATTERY_IN,
    CHARGING_RATE,
    DISCHARGING_RATE,
    SENSOR_TYPE,
    EXPORT,
    SIMULATED_SENSOR,
    ICON_CHARGING,
    ICON_DISCHARGING,
    ICON_FULL,
    ICON_EMPTY,
    PERCENTAGE_ENERGY_IMPORT_SAVED,
    MODE_CHARGING,
    MODE_FORCE_CHARGING,
    MODE_FULL,
    MODE_EMPTY,
    BATTERY_CYCLES,
    MESSAGE_TYPE_BATTERY_UPDATE,
    SENSOR_ID,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_MAP = {
    UnitOfEnergy.WATT_HOUR: SensorDeviceClass.ENERGY,
    UnitOfEnergy.KILO_WATT_HOUR: SensorDeviceClass.ENERGY,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    handle = hass.data[DOMAIN][config_entry.entry_id]
    sensors = await define_sensors(hass, handle)
    async_add_entities(sensors)


async def async_setup_platform(
    hass, configuration, async_add_entities, discovery_info=None
):
    if discovery_info is None:
        return

    for conf in discovery_info:
        battery = conf[CONF_BATTERY]
        handle = hass.data[DOMAIN][battery]
        sensors = await define_sensors(hass, handle)
        async_add_entities(sensors)


async def define_sensors(hass, handle):
    sensors = []
    sensors.append(
        DisplayOnlySensor(
            handle,
            ATTR_ENERGY_SAVED,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
        )
    )
    sensors.append(
        DisplayOnlySensor(
            handle,
            ATTR_ENERGY_BATTERY_OUT,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
        )
    )
    sensors.append(
        DisplayOnlySensor(
            handle,
            ATTR_ENERGY_BATTERY_IN,
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
        )
    )
    sensors.append(
        DisplayOnlySensor(
            handle, CHARGING_RATE, SensorDeviceClass.POWER, UnitOfPower.KILO_WATT
        )
    )
    sensors.append(
        DisplayOnlySensor(
            handle, DISCHARGING_RATE, SensorDeviceClass.POWER, UnitOfPower.KILO_WATT
        )
    )
    for input in handle._inputs:
        sensors.append(
            DisplayOnlySensor(
                handle,
                input[SIMULATED_SENSOR],
                SensorDeviceClass.ENERGY,
                UnitOfEnergy.KILO_WATT_HOUR,
            )
        )

    sensors.append(DisplayOnlySensor(handle, BATTERY_CYCLES, None, None))

    sensors.append(
        DisplayOnlySensor(
            handle,
            ATTR_MONEY_SAVED_IMPORT,
            SensorDeviceClass.MONETARY,
            hass.config.currency,
        )
    )
    sensors.append(
        DisplayOnlySensor(
            handle,
            ATTR_MONEY_SAVED,
            SensorDeviceClass.MONETARY,
            hass.config.currency,
        )
    )

    sensors.append(
        DisplayOnlySensor(
            handle,
            ATTR_MONEY_SAVED_EXPORT,
            SensorDeviceClass.MONETARY,
            hass.config.currency,
        )
    )
    sensors.append(SimulatedBattery(handle))
    sensors.append(BatteryStatus(handle, BATTERY_MODE))
    return sensors


class DisplayOnlySensor(RestoreEntity, SensorEntity):
    """
    Representation of a sensor.

    This reprisentation simply displays a value calculated
    in the __init__ file.
    """

    _attr_should_poll = False

    def __init__(self, handle, sensor_name, type_of_sensor, units):
        """Initialize the display only sensors for the battery."""
        self._handle = handle
        self._units = units
        self._name = f"{handle._name} ".replace("_", " ") + f"{sensor_name}".replace("_", " ").capitalize()
        self._attr_unique_id = f"{handle._name} - {sensor_name}"
        self._device_name = handle._name
        self._sensor_type = sensor_name
        self._type_of_sensor = type_of_sensor
        self._last_reset = dt_util.utcnow()
        self._available = False

    async def async_added_to_hass(self):
        """Subscribe for update from the battery."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()

        if state:
            try:
                self._handle._sensors[self._sensor_type] = float(state.state)
                self._last_reset = dt_util.as_utc(
                    dt_util.parse_datetime(state.attributes.get(ATTR_LAST_RESET))
                )
                self._available = True
                await self.async_update_ha_state(True)
            except Exception:
                _LOGGER.debug("Sensor state not restored properly.")
                self._available = False
        else:
            _LOGGER.debug("No sensor state - presume new battery.")
            self._available = False

        async def async_update_state():
            """Update sensor state."""
            if self._handle._sensors[self._sensor_type] is not None:
                self._available = True
            await self.async_update_ha_state(True)

        async_dispatcher_connect(
            self.hass,
            f"{self._device_name}-{MESSAGE_TYPE_BATTERY_UPDATE}",
            async_update_state,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return uniqueid."""
        return self._attr_unique_id

    @property
    def device_info(self):
        return {"name": self._device_name, "identifiers": {(DOMAIN, self._device_name)}}

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._sensor_type == ATTR_MONEY_SAVED:
            return round(float(self._handle._sensors[self._sensor_type]), 2)
        else:
            return round(float(self._handle._sensors[self._sensor_type]), 3)

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._type_of_sensor

    @property
    def state_class(self):
        """Return the device class of the sensor."""
        return SensorStateClass.TOTAL

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._units

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        state_attr = {}
        for input in self._handle._inputs:
            if self._sensor_type != input[SIMULATED_SENSOR]:
                break
            if input[SENSOR_TYPE] == EXPORT:
                break
            parent_sensor = input[SENSOR_ID]
            if self.hass.states.get(parent_sensor) is None or self.hass.states.get(
                parent_sensor
            ).state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
                break
            real_world_value = float(self.hass.states.get(parent_sensor).state)
            simulated_value = self._handle._sensors[self._sensor_type]
            if real_world_value == 0:
                _LOGGER.warning(
                    "Division by zero, real world: %s, simulated: %s, battery: %s",
                    real_world_value,
                    simulated_value,
                    self._name,
                )
                state_attr = {PERCENTAGE_ENERGY_IMPORT_SAVED: 0}
            else:
                percentage_value_saved = (
                    100 * (real_world_value - simulated_value) / real_world_value
                )
                state_attr = {
                    PERCENTAGE_ENERGY_IMPORT_SAVED: round(
                        float(percentage_value_saved), 0
                    )
                }
        return state_attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensor_type in [
            ATTR_MONEY_SAVED,
            ATTR_MONEY_SAVED_EXPORT,
            ATTR_MONEY_SAVED_IMPORT,
        ]:
            return round(float(self._handle._sensors[self._sensor_type]), 2)
        else:
            return round(float(self._handle._sensors[self._sensor_type]), 3)

    def update(self):
        """Not used."""
        return

    @property
    def last_reset(self):
        """Return the time when the sensor was last reset."""
        return self._last_reset

    @property
    def available(self) -> bool:
        """Needed to avoid spikes in energy dashboard on startup.
        Return True if entity is available.
        """
        return self._available


class SimulatedBattery(RestoreEntity, SensorEntity):
    """Representation of the battery itself."""

    _attr_should_poll = False

    def __init__(self, handle):
        self.handle = handle
        self._date_recording_started = time.asctime()
        self._name = f"{handle._name}"
        self._attr_unique_id = f"{handle._name}"

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state:
            self.handle._charge_state = min(
                float(state.state), self.handle._battery_size
            )
            if ATTR_DATE_RECORDING_STARTED in state.attributes:
                self.handle._date_recording_started = state.attributes[
                    ATTR_DATE_RECORDING_STARTED
                ]

        async def async_update_state():
            """Update sensor state."""
            await self.async_update_ha_state(True)

        async_dispatcher_connect(
            self.hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}", async_update_state
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return uniqueid."""
        return self._attr_unique_id

    @property
    def device_info(self):
        return {
            "name": self._name,
            "identifiers": {(DOMAIN, self.handle._name)},
        }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return round(float(self.handle._charge_state), 3)

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self):
        """Return the device class of the sensor."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        sensor_list = ""
        for input in self.handle._inputs:
            sensor_list = f"{sensor_list}, {input[SENSOR_ID]}"
        return {
            ATTR_STATUS: self.handle._sensors[BATTERY_MODE],
            ATTR_CHARGE_PERCENTAGE: int(self.handle._charge_percentage),
            ATTR_DATE_RECORDING_STARTED: self.handle._date_recording_started,
            CONF_BATTERY_SIZE: self.handle._battery_size,
            CONF_BATTERY_EFFICIENCY: float(self.handle._battery_efficiency),
            CONF_BATTERY_MAX_DISCHARGE_RATE: float(self.handle._max_discharge_rate),
            CONF_BATTERY_MAX_CHARGE_RATE: float(self.handle._max_charge_rate),
            ATTR_SOURCE_ID: sensor_list,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        if self.handle._sensors[BATTERY_MODE] in [MODE_CHARGING, MODE_FORCE_CHARGING]:
            return ICON_CHARGING
        if self.handle._sensors[BATTERY_MODE] == MODE_FULL:
            return ICON_FULL
        if self.handle._sensors[BATTERY_MODE] == MODE_EMPTY:
            return ICON_EMPTY
        return ICON_DISCHARGING

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(float(self.handle._charge_state), 3)


class BatteryStatus(SensorEntity):
    """Representation of the battery itself."""

    _attr_should_poll = False

    def __init__(self, handle, sensor_name):
        self.handle = handle
        self._date_recording_started = time.asctime()
        self._name = f"{handle._name} ".replace("_", " ") + f"{sensor_name}".replace("_", " ").capitalize()
        self._attr_unique_id = f"{handle._name} - {sensor_name}"
        self._device_name = handle._name
        self._sensor_type = sensor_name

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        async def async_update_state():
            """Update sensor state."""
            await self.async_update_ha_state(True)

        async_dispatcher_connect(
            self.hass,
            f"{self._device_name}-{MESSAGE_TYPE_BATTERY_UPDATE}",
            async_update_state,
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return uniqueid."""
        return self._attr_unique_id

    @property
    def device_info(self):
        return {"name": self._device_name, "identifiers": {(DOMAIN, self._device_name)}}

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.handle._sensors[BATTERY_MODE]

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.ENUM

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {}

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        if self.handle._sensors[BATTERY_MODE] in [MODE_CHARGING, MODE_FORCE_CHARGING]:
            return ICON_CHARGING
        if self.handle._sensors[BATTERY_MODE] == MODE_FULL:
            return ICON_FULL
        if self.handle._sensors[BATTERY_MODE] == MODE_EMPTY:
            return ICON_EMPTY
        return ICON_DISCHARGING

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.handle._sensors[BATTERY_MODE]
