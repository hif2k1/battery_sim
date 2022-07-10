import logging
from distutils import errors
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.components import sensor
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR
)
from .const import (
    DOMAIN, 
    BATTERY_OPTIONS, 
    BATTERY_TYPE, 
    CONF_BATTERY_SIZE, 
    CONF_BATTERY_MAX_DISCHARGE_RATE, 
    CONF_BATTERY_MAX_CHARGE_RATE, 
    CONF_BATTERY_EFFICIENCY,
    CONF_IMPORT_SENSOR,
    CONF_EXPORT_SENSOR,
    CONF_ENERGY_TARIFF,
    SETUP_TYPE,
    CONFIG_FLOW
)

import voluptuous as vol
from typing import Any

_LOGGER = logging.getLogger(__name__)

@config_entries.HANDLERS.register(DOMAIN)
class ExampleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""
    VERSION = 1

    async def async_step_user(self, user_input):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            if (user_input[BATTERY_TYPE] == "Custom"):
                return await self.async_step_custom()
            else:
                self._data = BATTERY_OPTIONS[user_input[BATTERY_TYPE]]
                self._data[CONF_NAME]=DOMAIN + ": " + user_input[BATTERY_TYPE]
                await self.async_set_unique_id(self._data[CONF_NAME])
                self._abort_if_unique_id_configured()
                return await self.async_step_connectsensors()

        battery_options_names = []
        for battery in BATTERY_OPTIONS:
            battery_options_names.append(battery)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                    vol.Required(BATTERY_TYPE): vol.In(battery_options_names),
                }),
        )

    async def async_step_custom(self, user_input = None):
        if user_input is not None:
            self._data = user_input
            self._data[CONF_NAME]=DOMAIN + ": " + str(user_input[CONF_BATTERY_SIZE]) + "_kWh_battery"
            await self.async_set_unique_id(self._data[CONF_NAME])
            self._abort_if_unique_id_configured()
            return await self.async_step_connectsensors()
        errors = {"base": "error message"}

        return self.async_show_form(
            step_id="custom",
            data_schema=vol.Schema({
                vol.Required(CONF_BATTERY_SIZE): vol.All(vol.Coerce(float)),
                vol.Required(CONF_BATTERY_MAX_DISCHARGE_RATE): vol.All(vol.Coerce(float)),
                vol.Required(CONF_BATTERY_MAX_CHARGE_RATE): vol.All(vol.Coerce(float)),
                vol.Required(CONF_BATTERY_EFFICIENCY, default=0.9): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            }),
        )

    async def async_step_connectsensors(self, user_input = None):
        if user_input is not None:
            self._data[CONF_IMPORT_SENSOR] = user_input[CONF_IMPORT_SENSOR]
            self._data[CONF_EXPORT_SENSOR] = user_input[CONF_EXPORT_SENSOR]
            self._data[CONF_ENERGY_TARIFF] = user_input[CONF_ENERGY_TARIFF]
            self._data[SETUP_TYPE] = CONFIG_FLOW
            return self.async_create_entry(title=self._data["name"], data=self._data)

        entities = self.hass.states.async_entity_ids()
        energy_entities = []
        for entity_id in entities:
            entity = self.hass.states.get(entity_id)
            if entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR or entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_WATT_HOUR:
                energy_entities.append(entity_id)
        return self.async_show_form(
            step_id="connectsensors",
            data_schema=vol.Schema({
                vol.Required(CONF_IMPORT_SENSOR): vol.In(energy_entities),
                vol.Required(CONF_EXPORT_SENSOR): vol.In(energy_entities),
                vol.Optional(CONF_ENERGY_TARIFF): vol.In(entities),
            }),
        )
