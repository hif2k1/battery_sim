"""Select platform for Battery Sim."""
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    CONF_BATTERY,
    OVERRIDE_CHARGING,
    PAUSE_BATTERY,
    FORCE_DISCHARGE,
    CHARGE_ONLY,
    DISCHARGE_ONLY,
    DEFAULT_MODE,
    ICON_FULL,
)

_LOGGER = logging.getLogger(__name__)

ATTR_BATTERY_MODE = "battery_mode"


async def async_setup_entry(hass, config_entry, async_add_entities):
    handle = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([BatteryMode(handle)])
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

    async_add_entities([BatteryMode(handle)])
    return True


class BatteryMode(RestoreEntity, SelectEntity):
    """Select to set the battery operating mode."""

    def __init__(self, handle):
        self.handle = handle
        self._device_name = handle._name
        self._device_identifier = handle.device_identifier
        self._name = f"{handle._name} ".replace("_", " ") + "Battery Mode"
        self._attr_unique_id = f"{handle._name} - Battery Mode"
        self._internal_options = [
            DEFAULT_MODE,
            OVERRIDE_CHARGING,
            PAUSE_BATTERY,
            FORCE_DISCHARGE,
            CHARGE_ONLY,
            DISCHARGE_ONLY,
        ]

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
        return ICON_FULL

    @property
    def current_option(self):
        return self.handle._battery_mode.replace("_", " ").capitalize()

    @property
    def options(self):
        return [opt.replace("_", " ").capitalize() for opt in self._internal_options]

    @property
    def extra_state_attributes(self):
        """Expose the internal mode key so it survives a restart unambiguously."""
        return {ATTR_BATTERY_MODE: self.handle._battery_mode}

    def _internal_option(self, option: str):
        """Map a displayed option back to its internal mode, or None if unknown."""
        return next(
            (
                opt
                for opt in self._internal_options
                if opt.replace("_", " ").capitalize() == option
            ),
            None,
        )

    async def async_select_option(self, option: str):
        internal_option = self._internal_option(option)

        if internal_option is None:
            _LOGGER.warning("Invalid option selected: %s", option)
            return

        self.handle._battery_mode = internal_option
        self.handle.async_trigger_update()
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Restore the mode that was selected before the last restart."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is None or state.state in (None, STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        # Prefer the internal key stored as an attribute; fall back to the
        # displayed option for states written before that attribute existed.
        restored_mode = state.attributes.get(ATTR_BATTERY_MODE)
        if restored_mode not in self._internal_options:
            restored_mode = self._internal_option(state.state)

        if restored_mode is None:
            _LOGGER.warning(
                "Ignoring invalid restored battery mode '%s' for '%s'.",
                state.state,
                self._name,
            )
            return

        self.handle._battery_mode = restored_mode
        _LOGGER.debug("Restored battery mode for '%s' to %s", self._name, restored_mode)
