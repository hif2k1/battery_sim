"""Switch  Platform Device for Battery Sim."""
import logging

from homeassistant.components.select import SelectEntity

from .const import (
    DOMAIN,
    CONF_BATTERY,
    OVERIDE_CHARGING,
    PAUSE_BATTERY,
    FORCE_DISCHARGE,
    CHARGE_ONLY,
    DISCHARGE_ONLY,
    DEFAULT_MODE,
    ICON_FULL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    handle = hass.data[DOMAIN][config_entry.entry_id]  # Get Handler

    battery_mode = BatteryMode(handle)
    async_add_entities([battery_mode])

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

    battery_mode = BatteryMode(handle)
    async_add_entities([battery_mode])
    return True


class BatteryMode(SelectEntity):
    """Switch to set the status of the Wiser Operation Mode (Away/Normal)."""

    def __init__(self, handle):
        """Initialize the sensor."""
        self.handle = handle
        self._device_name = handle._name
        self._name = f"{handle._name} - Battery Mode"
        self._options = [
            DEFAULT_MODE,
            OVERIDE_CHARGING,
            PAUSE_BATTERY,
            FORCE_DISCHARGE,
            CHARGE_ONLY,
            DISCHARGE_ONLY,
        ]
        self._current_option = DEFAULT_MODE

    @property
    def unique_id(self):
        """Return uniqueid."""
        return self._name

    @property
    def name(self):
        return self._name

    @property
    def device_info(self):
        return {
            "name": self._device_name,
            "identifiers": {(DOMAIN, self._device_name)},
        }

    @property
    def icon(self):
        """Return icon."""
        return ICON_FULL

    @property
    def current_option(self):
        """Return the state of the sensor."""
        return self._current_option

    @property
    def options(self):
        return self._options

    async def async_select_option(self, option: str):
        """Handle user selecting a new battery mode option."""

        # Store the selected option locally and in the handle
        self._current_option = option
        self.handle._battery_mode = option

        # Turn off all switches
        for switch in self.handle._switches:
            self.handle._switches[switch] = False

        # Only enable the selected switch if it exists
        if option in self.handle._switches:
            self.handle._switches[option] = True

        # Notify Home Assistant to refresh the UI/state
        self.schedule_update_ha_state(True)
        return True
