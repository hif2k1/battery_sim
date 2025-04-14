#from homeassistant.components.number import NumberEntity
from homeassistant.components.number import RestoreNumber
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import DiscoveryInfoType

from homeassistant.components.number import NumberEntity

from .const import DOMAIN
 
import logging

_LOGGER = logging.getLogger(__name__)

 
async def async_setup_entry(hass, config_entry, async_add_entities):
    handle = hass.data[DOMAIN][config_entry.entry_id]
    
    sliders = [
        BatterySlider(handle, slider_type="Charge Limit", key="charge_limit", icon="mdi:battery-charging-100")
    ]

    async_add_entities(sliders)

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

    sliders = [
        BatterySlider(handle, slider_type="Charge Limit", key="charge_limit", icon="mdi:battery-charging-100")
    ]

    async_add_entities(sliders)

    return True
    
    
class BatterySlider(RestoreNumber):
    """Slider to set a numeric parameter for the simulated battery."""

    def __init__(self, handle, slider_type, key, icon):
        """Initialize the slider."""
        self.handle = handle
        self._key = key
        self._icon = icon
        self._slider_type = slider_type
        self._device_name = handle._name
        self._name = f"{handle._name} - {slider_type}"
        self._max_value = handle._max_charge_rate
        self._value = self._max_value
        self._attr_icon = icon
        self._attr_unit_of_measurement = "kW"
        self._attr_mode = "box"
        
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
    def native_min_value(self):
        return 0.00

    @property
    def native_max_value(self):
        return self._max_value

    @property
    def native_step(self):
        return 0.01

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        self.handle.set_charge_limit(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Restore previously saved value."""
        await super().async_added_to_hass()

        if (last_number_data := await self.async_get_last_number_data()) is not None:
            self._value = last_number_data.native_value
            self.handle.set_charge_limit(self._value)  # Restore to handle too