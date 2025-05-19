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
    """Select to set the battery operating mode."""

    def __init__(self, handle):
        """Initialize the select entity."""
        self.handle = handle
        self._device_name = handle._name
        self._name = f"{handle._name} ".replace("_", " ") + "Battery Mode"
        self._attr_unique_id = f"{handle._name} - Battery Mode"

        # Internal options
        self._internal_options = [
            DEFAULT_MODE,
            OVERIDE_CHARGING,
            PAUSE_BATTERY,
            FORCE_DISCHARGE,
            CHARGE_ONLY,
            DISCHARGE_ONLY,
        ]

        # Current selected internal option
        self._current_internal_option = DEFAULT_MODE

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._attr_unique_id

    @property
    def name(self):
        """Return name."""
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
        """Return the label for the current selected internal option."""
        return self._current_internal_option.replace("_", " ").capitalize()

    @property
    def options(self):
        """Return the list of user-friendly labels."""
        return [opt.replace("_", " ").capitalize() for opt in self._internal_options]

    async def async_select_option(self, option: str):
        """Handle user selecting a new battery mode option."""
        # Convert the friendly label back to the internal option key
        internal_option = next(
            (opt for opt in self._internal_options if opt.replace("_", " ").capitalize() == option),
            None
        )

        if internal_option is None:
            _LOGGER.warning("Invalid option selected: %s", option)
            return

        # Store internal option
        self._current_internal_option = internal_option
        self.handle._battery_mode = internal_option

        # Reset all switches
        for switch in self.handle._switches:
            self.handle._switches[switch] = False

        # Enable the selected switch, if it exists
        if internal_option in self.handle._switches:
            self.handle._switches[internal_option] = True

        # Update Home Assistant state
        self.schedule_update_ha_state(True)
