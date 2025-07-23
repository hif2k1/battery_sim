"""Configuration flow for the Battery."""
import logging
import voluptuous as vol
import time

from homeassistant import config_entries
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
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
    IMPORT,
    EXPORT,
    SENSOR_ID,
    SENSOR_TYPE,
    TARIFF_SENSOR,
    FIXED_TARIFF,
    SIMULATED_SENSOR,
)
from .helpers import generate_input_list

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class BatterySetupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return flow options."""
        return BatteryOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            if user_input[BATTERY_TYPE] == "Custom":
                return await self.async_step_custom()

            self._data = BATTERY_OPTIONS[user_input[BATTERY_TYPE]]
            self._data[SETUP_TYPE] = CONFIG_FLOW
            self._data[CONF_NAME] = f"{user_input[BATTERY_TYPE]}"
            await self.async_set_unique_id(self._data[CONF_NAME])
            self._abort_if_unique_id_configured()
            self._data[CONF_INPUT_LIST] = []
            return await self.async_step_meter_menu()

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
            self._data[CONF_NAME] = f"{self._data[CONF_UNIQUE_NAME]}"
            self._data[CONF_INPUT_LIST] = []
            await self.async_set_unique_id(self._data[CONF_NAME])
            self._abort_if_unique_id_configured()
            return await self.async_step_meter_menu()

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
                    ),
                }
            ),
        )

    async def async_step_meter_menu(self, user_input=None):
        menu_options = ["add_import_meter", "add_export_meter"]
        import_meter: bool = False
        export_meter: bool = False
        for input in self._data[CONF_INPUT_LIST]:
            if input[SENSOR_TYPE] == IMPORT:
                import_meter = True
            if input[SENSOR_TYPE] == EXPORT:
                export_meter = True
        if import_meter and export_meter:
            menu_options.append("all_done")
        return self.async_show_menu(step_id="meter_menu", menu_options=menu_options)

    async def async_step_add_import_meter(self, user_input=None):
        if user_input is not None:
            self.current_input_entry: dict = {
                SENSOR_ID: user_input[SENSOR_ID],
                SENSOR_TYPE: IMPORT,
                SIMULATED_SENSOR: f"simulated_{user_input[SENSOR_ID]}",
            }
            return await self.async_step_tariff_menu()

        return self.async_show_form(
            step_id="add_import_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(SENSOR_ID): EntitySelector(
                        EntitySelectorConfig(device_class=SensorDeviceClass.ENERGY)
                    ),
                }
            ),
        )

    async def async_step_add_export_meter(self, user_input=None):
        if user_input is not None:
            self.current_input_entry: dict = {
                SENSOR_ID: user_input[SENSOR_ID],
                SENSOR_TYPE: EXPORT,
                SIMULATED_SENSOR: f"simulated_{user_input[SENSOR_ID]}",
            }
            return await self.async_step_tariff_menu()

        return self.async_show_form(
            step_id="add_export_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(SENSOR_ID): EntitySelector(
                        EntitySelectorConfig(device_class=SensorDeviceClass.ENERGY)
                    ),
                }
            ),
        )

    async def async_step_tariff_menu(self, user_input=None):
        return self.async_show_menu(
            step_id="tariff_menu",
            menu_options=["no_tariff_info", "fixed_tariff", "tariff_sensor"],
        )

    async def async_step_no_tariff_info(self, user_input=None):
        self.current_input_entry[TARIFF_TYPE] = NO_TARIFF_INFO
        self._data[CONF_INPUT_LIST].append(self.current_input_entry)
        return await self.async_step_meter_menu()

    async def async_step_fixed_tariff(self, user_input=None):
        if user_input is not None:
            self.current_input_entry[TARIFF_TYPE] = FIXED_TARIFF
            self.current_input_entry[FIXED_TARIFF] = user_input[FIXED_TARIFF]
            self._data[CONF_INPUT_LIST].append(self.current_input_entry)
            return await self.async_step_meter_menu()

        return self.async_show_form(
            step_id="fixed_tariff",
            data_schema=vol.Schema(
                {
                    vol.Optional(FIXED_TARIFF): vol.All(
                        vol.Coerce(float), vol.Range(min=0, max=10)
                    )
                }
            ),
        )

    async def async_step_tariff_sensor(self, user_input=None):
        if user_input is not None:
            self.current_input_entry[TARIFF_TYPE] = TARIFF_SENSOR
            self.current_input_entry[TARIFF_SENSOR] = user_input[TARIFF_SENSOR]
            self._data[CONF_INPUT_LIST].append(self.current_input_entry)
            return await self.async_step_meter_menu()

        return self.async_show_form(
            step_id="tariff_sensor",
            data_schema=vol.Schema(
                {vol.Required(TARIFF_SENSOR): EntitySelector(EntitySelectorConfig())}
            ),
        )

    async def async_step_all_done(self, user_input=None):
        return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)


class BatteryOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for battery."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.updated_entry = config_entry.data.copy()
        if CONF_INPUT_LIST not in self.updated_entry:
            self.updated_entry[CONF_INPUT_LIST] = generate_input_list(
                config=self.updated_entry
            )

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        return self.async_show_menu(
            step_id="init", menu_options=["main_params", "input_sensors", "all_done"]
        )

    async def async_step_main_params(self, user_input=None):
        if user_input is not None:
            self.updated_entry[CONF_BATTERY_SIZE] = user_input[CONF_BATTERY_SIZE]
            self.updated_entry[CONF_BATTERY_MAX_CHARGE_RATE] = user_input[
                CONF_BATTERY_MAX_CHARGE_RATE
            ]
            self.updated_entry[CONF_BATTERY_MAX_DISCHARGE_RATE] = user_input[
                CONF_BATTERY_MAX_DISCHARGE_RATE
            ]
            self.updated_entry[CONF_BATTERY_EFFICIENCY] = user_input[
                CONF_BATTERY_EFFICIENCY
            ]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self.updated_entry,
                options=self.config_entry.options,
            )
            return await self.async_step_init()

        data_schema = {
            vol.Required(
                CONF_BATTERY_SIZE, default=self.updated_entry[CONF_BATTERY_SIZE]
            ): vol.All(vol.Coerce(float)),
            vol.Required(
                CONF_BATTERY_MAX_CHARGE_RATE,
                default=self.updated_entry[CONF_BATTERY_MAX_CHARGE_RATE],
            ): vol.All(vol.Coerce(float)),
            vol.Required(
                CONF_BATTERY_MAX_DISCHARGE_RATE,
                default=self.updated_entry[CONF_BATTERY_MAX_DISCHARGE_RATE],
            ): vol.All(vol.Coerce(float)),
            vol.Required(
                CONF_BATTERY_EFFICIENCY,
                default=self.updated_entry[CONF_BATTERY_EFFICIENCY],
            ): vol.All(vol.Coerce(float)),
        }
        return self.async_show_form(
            step_id="main_params", data_schema=vol.Schema(data_schema)
        )

    async def async_step_input_sensors(self, user_input=None):
        """Handle options flow."""
        self.current_input_entry = None
        return self.async_show_menu(
            step_id="input_sensors",
            menu_options=[
                "add_import_meter",
                "add_export_meter",
                "edit_input_tariff",
                "delete_input",
            ],
        )

    async def async_step_delete_input(self, user_input=None):
        if user_input is not None:
            for input in self.updated_entry[CONF_INPUT_LIST]:
                if input[SENSOR_ID] == user_input[CONF_INPUT_LIST]:
                    self.updated_entry[CONF_INPUT_LIST].remove(input)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self.updated_entry,
                options=self.config_entry.options,
            )
            return await self.async_step_init()

        list_of_inputs = []
        for input in self.updated_entry[CONF_INPUT_LIST]:
            list_of_inputs.append(input[SENSOR_ID])

        data_schema = {
            vol.Required(CONF_INPUT_LIST): vol.In(list_of_inputs),
        }
        return self.async_show_form(
            step_id="delete_input", data_schema=vol.Schema(data_schema)
        )

    async def async_step_edit_input_tariff(self, user_input=None):
        if user_input is not None:
            for input in self.updated_entry[CONF_INPUT_LIST]:
                if input[SENSOR_ID] == user_input[CONF_INPUT_LIST]:
                    self.current_input_entry = input
            return await self.async_step_tariff_menu()

        list_of_inputs = []
        for input in self.updated_entry[CONF_INPUT_LIST]:
            list_of_inputs.append(input[SENSOR_ID])

        data_schema = {
            vol.Required(CONF_INPUT_LIST): vol.In(list_of_inputs),
        }
        return self.async_show_form(
            step_id="edit_input_tariff", data_schema=vol.Schema(data_schema)
        )

    async def async_step_add_import_meter(self, user_input=None):
        if user_input is not None:
            self.current_input_entry: dict = {
                SENSOR_ID: user_input[SENSOR_ID],
                SENSOR_TYPE: IMPORT,
                SIMULATED_SENSOR: f"simulated_{user_input[SENSOR_ID]}",
            }
            self.updated_entry[CONF_INPUT_LIST].append(self.current_input_entry)
            return await self.async_step_tariff_menu()

        return self.async_show_form(
            step_id="add_import_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(SENSOR_ID): EntitySelector(
                        EntitySelectorConfig(device_class=SensorDeviceClass.ENERGY)
                    ),
                }
            ),
        )

    async def async_step_add_export_meter(self, user_input=None):
        if user_input is not None:
            self.current_input_entry: dict = {
                SENSOR_ID: user_input[SENSOR_ID],
                SENSOR_TYPE: EXPORT,
                SIMULATED_SENSOR: f"simulated_{user_input[SENSOR_ID]}",
            }
            self.updated_entry[CONF_INPUT_LIST].append(self.current_input_entry)
            return await self.async_step_tariff_menu()

        return self.async_show_form(
            step_id="add_export_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(SENSOR_ID): EntitySelector(
                        EntitySelectorConfig(device_class=SensorDeviceClass.ENERGY)
                    ),
                }
            ),
        )

    async def async_step_tariff_menu(self, user_input=None):
        return self.async_show_menu(
            step_id="tariff_menu",
            menu_options=["no_tariff_info", "fixed_tariff", "tariff_sensor"],
        )

    async def async_step_no_tariff_info(self, user_input=None):
        self.current_input_entry[TARIFF_TYPE] = NO_TARIFF_INFO
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=self.updated_entry,
            options=self.config_entry.options,
        )
        return await self.async_step_init()

    async def async_step_fixed_tariff(self, user_input=None):
        if user_input is not None:
            self.current_input_entry[TARIFF_TYPE] = FIXED_TARIFF
            self.current_input_entry[FIXED_TARIFF] = user_input[FIXED_TARIFF]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self.updated_entry,
                options=self.config_entry.options,
            )
            return await self.async_step_init()

        current_val = self.current_input_entry.get(FIXED_TARIFF, None)

        return self.async_show_form(
            step_id="fixed_tariff",
            data_schema=vol.Schema(
                {
                    vol.Optional(FIXED_TARIFF, default=current_val): vol.All(
                        vol.Coerce(float),
                        vol.Range(min=0, max=10),
                    )
                }
            ),
        )

    async def async_step_tariff_sensor(self, user_input=None):
        if user_input is not None:
            self.current_input_entry[TARIFF_TYPE] = TARIFF_SENSOR
            self.current_input_entry[TARIFF_SENSOR] = user_input[TARIFF_SENSOR]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self.updated_entry,
                options=self.config_entry.options,
            )
            return await self.async_step_init()

        current_val = self.current_input_entry.get(TARIFF_SENSOR, None)

        return self.async_show_form(
            step_id="tariff_sensor",
            data_schema=vol.Schema(
                {vol.Required(TARIFF_SENSOR): EntitySelector(EntitySelectorConfig())}
            ),
        )

    async def async_step_all_done(self, user_input=None):
        data = {"time": time.asctime()}
        return self.async_create_entry(title="", data=data)
