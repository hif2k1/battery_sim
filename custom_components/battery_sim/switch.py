"""Switch platform for Battery Sim."""
import logging

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, CONF_BATTERY, PAUSE_BATTERY

_LOGGER = logging.getLogger(__name__)

BATTERY_SWITCHES = [
    {
        "name": PAUSE_BATTERY,
        "key": "pause_battery_enabled",
        "icon": "mdi:pause",
    }
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    handle = hass.data[DOMAIN][config_entry.entry_id]

    battery_switches = [
        BatterySwitch(handle, switch["name"], switch["key"], switch["icon"])
        for switch in BATTERY_SWITCHES
    ]
    async_add_entities(battery_switches)

    return True


async def async_setup_platform(
    hass, configuration, async_add_entities, discovery_info=None
):
    if discovery_info is None:
        _LOGGER.error("This platform is only available through discovery")
        return

    for conf in discovery_info:
        battery = conf[CONF_BATTERY]
        handle = hass.data[DOMAIN][battery]

    battery_switches = [
        BatterySwitch(handle, switch["name"], switch["key"], switch["icon"])
        for switch in BATTERY_SWITCHES
    ]
    async_add_entities(battery_switches)
    return True


class BatterySwitch(SwitchEntity):
    """Switch to pause or resume the simulated battery."""

    def __init__(self, handle, switch_type, key, icon):
        self.handle = handle
        self._key = key
        self._icon = icon
        self._switch_type = switch_type
        self._device_name = handle._name
        self._device_identifier = handle.device_identifier
        self._name = (
            f"{handle._name} ".replace("_", " ")
            + f"{switch_type}".replace("_", " ").capitalize()
        )
        self._attr_unique_id = f"{handle._name} - {switch_type}"
        self._type = type

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def name(self):
        return self._name

    @property
    def device_info(self):
        return {
            "name": self._device_name,
            "identifiers": {self._device_identifier},
        }

    @property
    def icon(self):
        return self._icon

    @property
    def is_on(self):
        return self.handle._switches[self._switch_type]

    async def async_turn_on(self, **kwargs):
        self.handle._switches[self._switch_type] = True
        self.handle.async_trigger_update()
        self.schedule_update_ha_state(True)
        return True

    async def async_turn_off(self, **kwargs):
        self.handle._switches[self._switch_type] = False
        self.handle.async_trigger_update()
        self.schedule_update_ha_state(True)
        return True
