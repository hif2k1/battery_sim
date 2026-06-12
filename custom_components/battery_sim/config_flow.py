"""Configuration flow for the Battery."""
import logging
import voluptuous as vol
import time

from homeassistant import config_entries
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
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
    CONF_BATTERY_CHARGE_EFFICIENCY,
    CONF_BATTERY_DISCHARGE_EFFICIENCY,
    CONF_BATTERY_EFFICIENCY,
    CONF_END_OF_LIFE_DEGRADATION,
    CONF_UPDATE_FREQUENCY,
    CONF_INPUT_LIST,
    CONF_RATED_BATTERY_CYCLES,
    CONF_SOLAR_ENERGY_SENSOR,
    CONF_NOMINAL_INVERTER_POWER,
    CONF_UNIQUE_NAME,
    CONF_MINIMUM_USER_SELECTABLE_SOC,
    DEFAULT_MINIMUM_USER_SELECTABLE_SOC,
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
from .helpers import (
    find_leftover_entity_registry_entries,
    generate_input_list,
    validate_efficiency_config,
)


EFFICIENCY_TEXT_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEXT)
)

_LOGGER = logging.getLogger(__name__)


def _current_tariff_sensor_value(input_entry):
    """Return the saved tariff sensor entity for a flow input entry."""
    return (input_entry or {}).get(TARIFF_SENSOR)


@config_entries.HANDLERS.register(DOMAIN)
class BatterySetupConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return flow options."""
        return BatteryOptionsFlowHandler(config_entry)

    @staticmethod
    def _validate_efficiency_fields(user_input):
        """Return field errors for invalid efficiency inputs."""
        errors = {}
        for key in (
            CONF_BATTERY_DISCHARGE_EFFICIENCY,
            CONF_BATTERY_CHARGE_EFFICIENCY,
        ):
            try:
                validate_efficiency_config(user_input[key])
            except (ValueError, TypeError):
                errors[key] = "invalid_input"
        return errors

    async def async_step_user(self, user_input):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            if user_input[BATTERY_TYPE] == "Custom":
                return await self.async_step_custom()

            self._data = BATTERY_OPTIONS[user_input[BATTERY_TYPE]]
            self._data[SETUP_TYPE] = CONFIG_FLOW
            self._data[CONF_NAME] = f"{user_input[BATTERY_TYPE]}"
            self._data[CONF_RATED_BATTERY_CYCLES] = 6000
            self._data[CONF_END_OF_LIFE_DEGRADATION] = 0.8
            self._data[CONF_UPDATE_FREQUENCY] = 60
            self._data[CONF_MINIMUM_USER_SELECTABLE_SOC] = (
                DEFAULT_MINIMUM_USER_SELECTABLE_SOC
            )
            await self.async_set_unique_id(self._data[CONF_NAME])
            self._abort_if_unique_id_configured(reload_on_update=False)
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
        errors = {}
        if user_input is not None:
            errors = self._validate_efficiency_fields(user_input)
            if not errors:
                self._data = user_input
                self._data[SETUP_TYPE] = CONFIG_FLOW
                self._data[CONF_NAME] = f"{self._data[CONF_UNIQUE_NAME]}"
                self._data[CONF_INPUT_LIST] = []
                solar_sensor = user_input.get(CONF_SOLAR_ENERGY_SENSOR)
                if solar_sensor:
                    self._data[CONF_SOLAR_ENERGY_SENSOR] = solar_sensor
                else:
                    self._data.pop(CONF_SOLAR_ENERGY_SENSOR, None)

                nominal_inverter_power = user_input.get(CONF_NOMINAL_INVERTER_POWER)
                if nominal_inverter_power is not None:
                    self._data[CONF_NOMINAL_INVERTER_POWER] = nominal_inverter_power
                else:
                    self._data.pop(CONF_NOMINAL_INVERTER_POWER, None)
                await self.async_set_unique_id(self._data[CONF_NAME])
                self._abort_if_unique_id_configured(reload_on_update=False)
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
                    vol.Required(
                        CONF_BATTERY_DISCHARGE_EFFICIENCY, default="0.9"
                    ): EFFICIENCY_TEXT_SELECTOR,
                    vol.Required(
                        CONF_BATTERY_CHARGE_EFFICIENCY, default="0.9"
                    ): EFFICIENCY_TEXT_SELECTOR,
                     vol.Required(CONF_RATED_BATTERY_CYCLES, default=6000): vol.All(
                        vol.Coerce(float), vol.Range(min=1)
                    ),
                    vol.Required(CONF_END_OF_LIFE_DEGRADATION, default=0.8): vol.All(
                        vol.Coerce(float), vol.Range(min=0, max=1)
                    ),
                    vol.Required(CONF_UPDATE_FREQUENCY, default=60): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                    vol.Required(
                        CONF_MINIMUM_USER_SELECTABLE_SOC,
                        default=DEFAULT_MINIMUM_USER_SELECTABLE_SOC,
                    ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
                    vol.Optional(CONF_SOLAR_ENERGY_SENSOR): EntitySelector(
                        EntitySelectorConfig(device_class=SensorDeviceClass.ENERGY)
                    ),
                    vol.Optional(CONF_NOMINAL_INVERTER_POWER): vol.All(
                        vol.Coerce(float), vol.Range(min=0)
                    ),
                }
            ),
            errors=errors,
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
                        vol.Coerce(float), vol.Range(min=0, max=100)
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

        current_val = _current_tariff_sensor_value(self.current_input_entry)

        return self.async_show_form(
            step_id="tariff_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        TARIFF_SENSOR,
                        description={"suggested_value": current_val},
                    ): EntitySelector(EntitySelectorConfig())
                }
            ),
        )

    async def async_step_all_done(self, user_input=None):
        return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)


class BatteryOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for battery."""

    def __init__(self, config_entry=None):
        """Initialize options flow."""
        self._config_entry_compat = config_entry
        self.updated_entry = None
        self.current_input_entry = None

    @property
    def _battery_config_entry(self):
        """Return the config entry for both old and new Home Assistant cores."""
        return getattr(self, "config_entry", None) or self._config_entry_compat

    @staticmethod
    def _validate_efficiency_fields(user_input):
        """Return field errors for invalid efficiency inputs."""
        errors = {}
        for key in (
            CONF_BATTERY_DISCHARGE_EFFICIENCY,
            CONF_BATTERY_CHARGE_EFFICIENCY,
        ):
            try:
                validate_efficiency_config(user_input[key])
            except (ValueError, TypeError):
                errors[key] = "invalid_input"
        return errors

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        config_entry = self._battery_config_entry
        self.updated_entry = config_entry.data.copy()
        self._active_config_entry = config_entry
        if CONF_INPUT_LIST not in self.updated_entry:
            self.updated_entry[CONF_INPUT_LIST] = generate_input_list(
                config=self.updated_entry
            )

        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "main_params",
                "input_sensors",
                "delete_leftover_entities",
                "all_done",
            ],
        )

    async def async_step_delete_leftover_entities(self, user_input=None):
        """Delete stale entity registry entries for this battery."""
        entity_reg = er.async_get(self.hass)
        device_reg = dr.async_get(self.hass)
        leftovers = find_leftover_entity_registry_entries(
            entity_reg,
            device_reg,
            self.updated_entry,
            self._active_config_entry.entry_id,
        )
        if not leftovers:
            _LOGGER.warning(
                "No leftover Battery Sim entities found for '%s'.",
                self.updated_entry[CONF_NAME],
            )
            return await self.async_step_init()

        leftover_entity_ids = [entry.entity_id for entry in leftovers]
        for entry in leftovers:
            entity_reg.async_remove(entry.entity_id)

        _LOGGER.warning(
            "Deleted leftover Battery Sim entities for '%s': %s",
            self.updated_entry[CONF_NAME],
            ", ".join(leftover_entity_ids),
        )
        return await self.async_step_init()

    async def async_step_main_params(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = self._validate_efficiency_fields(user_input)
            if not errors:
                self.updated_entry[CONF_BATTERY_SIZE] = user_input[CONF_BATTERY_SIZE]
                self.updated_entry[CONF_BATTERY_MAX_CHARGE_RATE] = user_input[
                    CONF_BATTERY_MAX_CHARGE_RATE
                ]
                self.updated_entry[CONF_BATTERY_MAX_DISCHARGE_RATE] = user_input[
                    CONF_BATTERY_MAX_DISCHARGE_RATE
                ]
                self.updated_entry[CONF_BATTERY_DISCHARGE_EFFICIENCY] = user_input[
                    CONF_BATTERY_DISCHARGE_EFFICIENCY
                ]
                self.updated_entry[CONF_BATTERY_CHARGE_EFFICIENCY] = user_input[
                    CONF_BATTERY_CHARGE_EFFICIENCY
                ]
                self.updated_entry[CONF_RATED_BATTERY_CYCLES] = user_input[
                    CONF_RATED_BATTERY_CYCLES
                ]
                self.updated_entry[CONF_END_OF_LIFE_DEGRADATION] = user_input[
                    CONF_END_OF_LIFE_DEGRADATION
                ]
                self.updated_entry.pop(CONF_BATTERY_EFFICIENCY, None)
                self.updated_entry[CONF_UPDATE_FREQUENCY] = user_input[
                    CONF_UPDATE_FREQUENCY
                ]
                self.updated_entry[CONF_MINIMUM_USER_SELECTABLE_SOC] = user_input[
                    CONF_MINIMUM_USER_SELECTABLE_SOC
                ]
                if user_input.get(CONF_SOLAR_ENERGY_SENSOR):
                    self.updated_entry[CONF_SOLAR_ENERGY_SENSOR] = user_input[
                        CONF_SOLAR_ENERGY_SENSOR
                    ]
                else:
                    self.updated_entry.pop(CONF_SOLAR_ENERGY_SENSOR, None)
                if user_input.get(CONF_NOMINAL_INVERTER_POWER) is not None:
                    self.updated_entry[CONF_NOMINAL_INVERTER_POWER] = user_input[
                        CONF_NOMINAL_INVERTER_POWER
                    ]
                else:
                    self.updated_entry.pop(CONF_NOMINAL_INVERTER_POWER, None)
                self.hass.config_entries.async_update_entry(
                    self._active_config_entry,
                    data=self.updated_entry,
                    options=self._active_config_entry.options,
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
            # Use .get() so existing entries using legacy `efficiency` keep working.
            vol.Required(
                CONF_BATTERY_DISCHARGE_EFFICIENCY,
                default=str(
                    self.updated_entry.get(
                        CONF_BATTERY_DISCHARGE_EFFICIENCY,
                        self.updated_entry.get(CONF_BATTERY_EFFICIENCY, 0.9),
                    )
                ),
            ): EFFICIENCY_TEXT_SELECTOR,
            vol.Required(
                CONF_BATTERY_CHARGE_EFFICIENCY,
                default=str(
                    self.updated_entry.get(
                        CONF_BATTERY_CHARGE_EFFICIENCY,
                        self.updated_entry.get(CONF_BATTERY_EFFICIENCY, 1.0),
                    )
                ),
            ): EFFICIENCY_TEXT_SELECTOR,
            vol.Required(
                CONF_RATED_BATTERY_CYCLES,
                default=self.updated_entry.get(CONF_RATED_BATTERY_CYCLES, 6000),
            ): vol.All(vol.Coerce(float), vol.Range(min=1)),
            vol.Required(
                CONF_END_OF_LIFE_DEGRADATION,
                default=self.updated_entry.get(CONF_END_OF_LIFE_DEGRADATION, 0.8),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Required(
                CONF_UPDATE_FREQUENCY,
                default=self.updated_entry.get(CONF_UPDATE_FREQUENCY, 60),
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(
                CONF_MINIMUM_USER_SELECTABLE_SOC,
                default=self.updated_entry.get(
                    CONF_MINIMUM_USER_SELECTABLE_SOC,
                    DEFAULT_MINIMUM_USER_SELECTABLE_SOC,
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(
                CONF_SOLAR_ENERGY_SENSOR,
                description={
                    "suggested_value": self.updated_entry.get(CONF_SOLAR_ENERGY_SENSOR)
                },
            ): EntitySelector(
                EntitySelectorConfig(device_class=SensorDeviceClass.ENERGY)
            ),
            vol.Optional(
                CONF_NOMINAL_INVERTER_POWER,
                default=self.updated_entry.get(CONF_NOMINAL_INVERTER_POWER),
            ): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=0))),
        }
        return self.async_show_form(
            step_id="main_params",
            data_schema=vol.Schema(data_schema),
            errors=errors,
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
                self._active_config_entry,
                data=self.updated_entry,
                options=self._active_config_entry.options,
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
            self._active_config_entry,
            data=self.updated_entry,
            options=self._active_config_entry.options,
        )
        return await self.async_step_init()

    async def async_step_fixed_tariff(self, user_input=None):
        if user_input is not None:
            self.current_input_entry[TARIFF_TYPE] = FIXED_TARIFF
            self.current_input_entry[FIXED_TARIFF] = user_input[FIXED_TARIFF]
            self.hass.config_entries.async_update_entry(
                self._active_config_entry,
                data=self.updated_entry,
                options=self._active_config_entry.options,
            )
            return await self.async_step_init()

        current_val = self.current_input_entry.get(FIXED_TARIFF, None)

        return self.async_show_form(
            step_id="fixed_tariff",
            data_schema=vol.Schema(
                {
                    vol.Optional(FIXED_TARIFF, default=current_val): vol.All(
                        vol.Coerce(float),
                        vol.Range(min=0, max=100),
                    )
                }
            ),
        )

    async def async_step_tariff_sensor(self, user_input=None):
        if user_input is not None:
            self.current_input_entry[TARIFF_TYPE] = TARIFF_SENSOR
            self.current_input_entry[TARIFF_SENSOR] = user_input[TARIFF_SENSOR]
            self.hass.config_entries.async_update_entry(
                self._active_config_entry,
                data=self.updated_entry,
                options=self._active_config_entry.options,
            )
            return await self.async_step_init()

        current_val = _current_tariff_sensor_value(self.current_input_entry)

        return self.async_show_form(
            step_id="tariff_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        TARIFF_SENSOR,
                        description={"suggested_value": current_val},
                    ): EntitySelector(EntitySelectorConfig())
                }
            ),
        )

    async def async_step_all_done(self, user_input=None):
        data = {"time": time.asctime()}
        return self.async_create_entry(title="", data=data)
