"""Configuration flow for the Battery."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME
from .const import (
    DOMAIN,
    BATTERY_OPTIONS,
    BATTERY_TYPE,
    CONF_BATTERY_SIZE,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_EFFICIENCY,
    CONF_INPUT_LIST,
    CONF_UNIQUE_NAME,
    SETUP_TYPE,
    CONFIG_FLOW,
    TARIFF_TYPE,
    NO_TARIFF_INFO,
    TARIFF_SENSOR_ENTITIES,
    FIXED_NUMERICAL_TARIFFS,
    IMPORT,
    EXPORT,
    SENSOR_ID,
    SENSOR_TYPE,
    NEXT_STEP,
    ADD_ANOTHER,
    ALL_DONE,
    TARIFF_SENSOR,
    FIXED_TARIFF,
    SIMULATED_SENSOR
)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class ExampleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""

    VERSION = 1

    async def async_step_user(self, user_input):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            if user_input[BATTERY_TYPE] == "Custom":
                return await self.async_step_custom()

            self._data = BATTERY_OPTIONS[user_input[BATTERY_TYPE]]
            self._data[SETUP_TYPE] = CONFIG_FLOW
            self._data[CONF_NAME] = f"{DOMAIN}: { user_input[BATTERY_TYPE]}"
            await self.async_set_unique_id(self._data[CONF_NAME])
            self._abort_if_unique_id_configured()
            self._data[CONF_INPUT_LIST] = []
            return await self.async_step_addmeter()

        battery_options_names = list(BATTERY_OPTIONS)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(BATTERY_TYPE): vol.In(battery_options_names),
                }
            ),
        )

    async def async_step_custom(self, user_input=None):
        if user_input is not None:
            self._data = user_input
            self._data[SETUP_TYPE] = CONFIG_FLOW
            self._data[CONF_NAME] = f"{DOMAIN}: {self._data[CONF_UNIQUE_NAME]}"
            await self.async_set_unique_id(self._data[CONF_NAME])
            self._abort_if_unique_id_configured()
            return await self.async_step_addmeter()

        return self.async_show_form(
            step_id="custom",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UNIQUE_NAME): vol.All(str),
                    vol.Required(CONF_BATTERY_SIZE): vol.All(vol.Coerce(float)),
                    vol.Required(CONF_BATTERY_MAX_DISCHARGE_RATE): vol.All(
                        vol.Coerce(float)
                    ),
                    vol.Required(CONF_BATTERY_MAX_CHARGE_RATE): vol.All(
                        vol.Coerce(float)
                    ),
                    vol.Required(CONF_BATTERY_EFFICIENCY, default=0.9): vol.All(
                        vol.Coerce(float), vol.Range(min=0, max=1)
                    )
                }
            )
        )

    async def async_step_addmeter(self, user_input=None):
        """Handle a flow initialized by the user."""

        errors = {}
        if user_input is not None:
            input_entry: dict = {
                SENSOR_ID : user_input[SENSOR_ID],
                SENSOR_TYPE : user_input[SENSOR_TYPE],
                SIMULATED_SENSOR: f"simulated_{user_input[SENSOR_ID]}"
            }
            if user_input[TARIFF_TYPE] == NO_TARIFF_INFO:
                input_entry[TARIFF_TYPE] = NO_TARIFF_INFO
            elif user_input[TARIFF_TYPE] == FIXED_NUMERICAL_TARIFFS:
                input_entry[TARIFF_TYPE] = FIXED_TARIFF
                if FIXED_TARIFF in user_input:
                    input_entry[FIXED_TARIFF] = user_input[FIXED_TARIFF]
                else:
                    errors["base"] = "Fixed tariff selected, but no number found."
            elif user_input[TARIFF_TYPE] == TARIFF_SENSOR_ENTITIES:
                input_entry[TARIFF_TYPE] = TARIFF_SENSOR
                if TARIFF_SENSOR in user_input:
                    input_entry[TARIFF_SENSOR] = user_input[TARIFF_SENSOR]
                else:
                    errors["base"] = "Tariff type sensor selected, but no sensor provided."

            self._data[CONF_INPUT_LIST].append(input_entry)

            if "base" not in errors and user_input[NEXT_STEP] == ADD_ANOTHER:
                return await self.async_step_addmeter()
            elif "base" not in errors and user_input[NEXT_STEP] == ALL_DONE:
                import_meter: bool = False
                export_meter: bool = False
                for input in self._data[CONF_INPUT_LIST]:
                    if input[SENSOR_TYPE] == IMPORT: import_meter = True
                    if input[SENSOR_TYPE] == EXPORT: export_meter = True
                if import_meter and export_meter:
                    return self.async_create_entry(
                        title = self._data[CONF_NAME],
                        data = self._data
                    )
                else: 
                    errors["base"] = "At least one import and one export meter are needed for the battery to work."

        meter_types = [
            IMPORT,
            EXPORT,
        ]
        tariff_types = [
            NO_TARIFF_INFO,
            TARIFF_SENSOR_ENTITIES,
            FIXED_NUMERICAL_TARIFFS
        ]
        next_step = [
            ADD_ANOTHER,
            ALL_DONE
        ]

        data_schema = vol.Schema(
                {
                    vol.Required(SENSOR_ID): EntitySelector(
                        EntitySelectorConfig(device_class=SensorDeviceClass.ENERGY)
                    ),
                    vol.Required(SENSOR_TYPE): vol.In(meter_types),
                    vol.Required(TARIFF_TYPE): vol.In(tariff_types),
                    vol.Optional(TARIFF_SENSOR): EntitySelector(
                        EntitySelectorConfig()
                    ),
                    vol.Optional(FIXED_TARIFF): vol.All(
                        vol.Coerce(float), vol.Range(min=0, max=10)
                    ),
                    vol.Required(NEXT_STEP): vol.In(next_step),
                }
            )
        
        return self.async_show_form(
            step_id = "addmeter",
            data_schema = data_schema,
            errors = errors
        )