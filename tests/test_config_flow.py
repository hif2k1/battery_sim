"""Tests for the battery_sim config and options flows."""
import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.battery_sim.const import (
    BATTERY_TYPE,
    CONF_BATTERY_CHARGE_EFFICIENCY,
    CONF_BATTERY_DISCHARGE_EFFICIENCY,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_SIZE,
    CONF_END_OF_LIFE_DEGRADATION,
    CONF_INPUT_LIST,
    CONF_MINIMUM_USER_SELECTABLE_SOC,
    CONF_NOMINAL_INVERTER_POWER,
    CONF_RATED_BATTERY_CYCLES,
    CONF_SOLAR_ENERGY_SENSOR,
    CONF_UNIQUE_NAME,
    CONF_UPDATE_FREQUENCY,
    DOMAIN,
    EXPORT,
    FIXED_TARIFF,
    IMPORT,
    NO_TARIFF_INFO,
    SENSOR_ID,
    SENSOR_TYPE,
    TARIFF_SENSOR,
    TARIFF_TYPE,
)

from pytest_homeassistant_custom_component.common import MockConfigEntry

from .common import (
    EXPORT_SENSOR_ID,
    IMPORT_SENSOR_ID,
    IMPORT_TARIFF_SENSOR_ID,
    base_config,
)

CUSTOM_BATTERY_INPUT = {
    CONF_UNIQUE_NAME: "My Custom Battery",
    CONF_BATTERY_SIZE: 11.0,
    CONF_BATTERY_MAX_DISCHARGE_RATE: 6.0,
    CONF_BATTERY_MAX_CHARGE_RATE: 5.0,
    CONF_BATTERY_DISCHARGE_EFFICIENCY: "0.9",
    CONF_BATTERY_CHARGE_EFFICIENCY: "0:0.85, 5:0.95",
    CONF_RATED_BATTERY_CYCLES: 5000,
    CONF_END_OF_LIFE_DEGRADATION: 0.7,
    CONF_UPDATE_FREQUENCY: 30,
    CONF_MINIMUM_USER_SELECTABLE_SOC: 0.05,
}


async def select_menu_option(hass, flow_id, option):
    """Choose an option from a menu step."""
    return await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": option}
    )


async def add_meter(hass, flow_id, meter_step, sensor_id, tariff_step, tariff_input):
    """Walk through adding one meter including its tariff sub-flow."""
    result = await select_menu_option(hass, flow_id, meter_step)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        flow_id, {SENSOR_ID: sensor_id}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "tariff_menu"

    result = await select_menu_option(hass, flow_id, tariff_step)
    if tariff_input is not None:
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            flow_id, tariff_input
        )
    return result


async def test_user_flow_with_predefined_battery(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {BATTERY_TYPE: "Tesla Powerwall"}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "meter_menu"
    # Both meter types are still missing, so the flow cannot finish yet.
    assert "all_done" not in result["menu_options"]

    flow_id = result["flow_id"]
    result = await add_meter(
        hass, flow_id, "add_import_meter", IMPORT_SENSOR_ID, "no_tariff_info", None
    )
    assert result["step_id"] == "meter_menu"
    assert "all_done" not in result["menu_options"]

    result = await add_meter(
        hass,
        flow_id,
        "add_export_meter",
        EXPORT_SENSOR_ID,
        "fixed_tariff",
        {FIXED_TARIFF: 0.15},
    )
    assert result["step_id"] == "meter_menu"
    assert "all_done" in result["menu_options"]

    result = await select_menu_option(hass, flow_id, "all_done")
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tesla Powerwall"
    data = result["data"]
    assert data[CONF_NAME] == "Tesla Powerwall"
    assert data[CONF_BATTERY_SIZE] == 13.5
    assert len(data[CONF_INPUT_LIST]) == 2
    import_input, export_input = data[CONF_INPUT_LIST]
    assert import_input[SENSOR_TYPE] == IMPORT
    assert import_input[SENSOR_ID] == IMPORT_SENSOR_ID
    assert import_input[TARIFF_TYPE] == NO_TARIFF_INFO
    assert export_input[SENSOR_TYPE] == EXPORT
    assert export_input[TARIFF_TYPE] == FIXED_TARIFF
    assert export_input[FIXED_TARIFF] == 0.15


async def test_user_flow_aborts_for_duplicate_battery(hass):
    MockConfigEntry(
        domain=DOMAIN, data=base_config(), unique_id="Tesla Powerwall"
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {BATTERY_TYPE: "Tesla Powerwall"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_custom_battery_flow(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {BATTERY_TYPE: "Custom"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom"

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id, dict(CUSTOM_BATTERY_INPUT)
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "meter_menu"

    result = await add_meter(
        hass,
        flow_id,
        "add_import_meter",
        IMPORT_SENSOR_ID,
        "tariff_sensor",
        {TARIFF_SENSOR: IMPORT_TARIFF_SENSOR_ID},
    )
    result = await add_meter(
        hass, flow_id, "add_export_meter", EXPORT_SENSOR_ID, "no_tariff_info", None
    )
    result = await select_menu_option(hass, flow_id, "all_done")
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = result["data"]
    assert data[CONF_NAME] == "My Custom Battery"
    assert data[CONF_BATTERY_SIZE] == 11.0
    assert data[CONF_BATTERY_CHARGE_EFFICIENCY] == "0:0.85, 5:0.95"
    assert CONF_SOLAR_ENERGY_SENSOR not in data
    assert CONF_NOMINAL_INVERTER_POWER not in data
    import_input = data[CONF_INPUT_LIST][0]
    assert import_input[TARIFF_TYPE] == TARIFF_SENSOR
    assert import_input[TARIFF_SENSOR] == IMPORT_TARIFF_SENSOR_ID


async def test_custom_battery_flow_rejects_invalid_efficiency(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {BATTERY_TYPE: "Custom"}
    )

    bad_input = dict(CUSTOM_BATTERY_INPUT)
    bad_input[CONF_BATTERY_DISCHARGE_EFFICIENCY] = "not a number"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], bad_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom"
    assert result["errors"] == {CONF_BATTERY_DISCHARGE_EFFICIENCY: "invalid_input"}


async def test_custom_battery_flow_with_solar(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {BATTERY_TYPE: "Custom"}
    )

    flow_id = result["flow_id"]
    custom_input = dict(CUSTOM_BATTERY_INPUT)
    custom_input[CONF_UNIQUE_NAME] = "Solar Custom Battery"
    custom_input[CONF_SOLAR_ENERGY_SENSOR] = "sensor.solar_production"
    custom_input[CONF_NOMINAL_INVERTER_POWER] = 3.6
    result = await hass.config_entries.flow.async_configure(flow_id, custom_input)
    assert result["type"] is FlowResultType.MENU

    await add_meter(
        hass, flow_id, "add_import_meter", IMPORT_SENSOR_ID, "no_tariff_info", None
    )
    await add_meter(
        hass, flow_id, "add_export_meter", EXPORT_SENSOR_ID, "no_tariff_info", None
    )
    result = await select_menu_option(hass, flow_id, "all_done")
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SOLAR_ENERGY_SENSOR] == "sensor.solar_production"
    assert result["data"][CONF_NOMINAL_INVERTER_POWER] == 3.6


class TestOptionsFlow:
    """Tests for the options flow."""

    async def _start_options(self, hass, entry):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "init"
        return result

    async def test_main_params_update(self, hass, setup_battery):
        entry, _handle = await setup_battery()
        result = await self._start_options(hass, entry)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "main_params"}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_BATTERY_SIZE: 12.0,
                CONF_BATTERY_MAX_CHARGE_RATE: 3.0,
                CONF_BATTERY_MAX_DISCHARGE_RATE: 6.0,
                CONF_BATTERY_DISCHARGE_EFFICIENCY: "0.95",
                CONF_BATTERY_CHARGE_EFFICIENCY: "0:0.8, 4:0.9",
                CONF_RATED_BATTERY_CYCLES: 4000,
                CONF_END_OF_LIFE_DEGRADATION: 0.75,
                CONF_UPDATE_FREQUENCY: 120,
                CONF_MINIMUM_USER_SELECTABLE_SOC: 0.2,
            },
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "init"
        await hass.async_block_till_done()

        assert entry.data[CONF_BATTERY_SIZE] == 12.0
        assert entry.data[CONF_BATTERY_CHARGE_EFFICIENCY] == "0:0.8, 4:0.9"
        assert entry.data[CONF_UPDATE_FREQUENCY] == 120
        # The reload created a fresh handle with the new configuration.
        new_handle = hass.data[DOMAIN][entry.entry_id]
        assert new_handle._battery_size == 12.0

    async def test_main_params_rejects_invalid_efficiency(self, hass, setup_battery):
        entry, _handle = await setup_battery()
        result = await self._start_options(hass, entry)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "main_params"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_BATTERY_SIZE: 12.0,
                CONF_BATTERY_MAX_CHARGE_RATE: 3.0,
                CONF_BATTERY_MAX_DISCHARGE_RATE: 6.0,
                CONF_BATTERY_DISCHARGE_EFFICIENCY: "bogus",
                CONF_BATTERY_CHARGE_EFFICIENCY: "0.9",
                CONF_RATED_BATTERY_CYCLES: 4000,
                CONF_END_OF_LIFE_DEGRADATION: 0.75,
                CONF_UPDATE_FREQUENCY: 120,
                CONF_MINIMUM_USER_SELECTABLE_SOC: 0.2,
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {
            CONF_BATTERY_DISCHARGE_EFFICIENCY: "invalid_input"
        }

    async def test_add_import_meter(self, hass, setup_battery):
        entry, _handle = await setup_battery()
        result = await self._start_options(hass, entry)
        flow_id = result["flow_id"]

        result = await hass.config_entries.options.async_configure(
            flow_id, {"next_step_id": "input_sensors"}
        )
        assert result["type"] is FlowResultType.MENU

        result = await hass.config_entries.options.async_configure(
            flow_id, {"next_step_id": "add_import_meter"}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            flow_id, {SENSOR_ID: "sensor.second_import_energy"}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "tariff_menu"

        result = await hass.config_entries.options.async_configure(
            flow_id, {"next_step_id": "tariff_sensor"}
        )
        result = await hass.config_entries.options.async_configure(
            flow_id, {TARIFF_SENSOR: IMPORT_TARIFF_SENSOR_ID}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "init"
        await hass.async_block_till_done()

        inputs = entry.data[CONF_INPUT_LIST]
        assert len(inputs) == 3
        assert inputs[2][SENSOR_ID] == "sensor.second_import_energy"
        assert inputs[2][SENSOR_TYPE] == IMPORT
        assert inputs[2][TARIFF_SENSOR] == IMPORT_TARIFF_SENSOR_ID

    async def test_delete_input(self, hass, setup_battery):
        entry, _handle = await setup_battery()
        result = await self._start_options(hass, entry)
        flow_id = result["flow_id"]

        await hass.config_entries.options.async_configure(
            flow_id, {"next_step_id": "input_sensors"}
        )
        result = await hass.config_entries.options.async_configure(
            flow_id, {"next_step_id": "delete_input"}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            flow_id, {CONF_INPUT_LIST: IMPORT_SENSOR_ID}
        )
        assert result["type"] is FlowResultType.MENU
        await hass.async_block_till_done()

        inputs = entry.data[CONF_INPUT_LIST]
        assert len(inputs) == 1
        assert inputs[0][SENSOR_ID] == EXPORT_SENSOR_ID

    async def test_edit_input_tariff(self, hass, setup_battery):
        entry, _handle = await setup_battery()
        result = await self._start_options(hass, entry)
        flow_id = result["flow_id"]

        await hass.config_entries.options.async_configure(
            flow_id, {"next_step_id": "input_sensors"}
        )
        result = await hass.config_entries.options.async_configure(
            flow_id, {"next_step_id": "edit_input_tariff"}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            flow_id, {CONF_INPUT_LIST: IMPORT_SENSOR_ID}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "tariff_menu"

        result = await hass.config_entries.options.async_configure(
            flow_id, {"next_step_id": "fixed_tariff"}
        )
        result = await hass.config_entries.options.async_configure(
            flow_id, {FIXED_TARIFF: 0.42}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "init"
        await hass.async_block_till_done()

        import_input = entry.data[CONF_INPUT_LIST][0]
        assert import_input[TARIFF_TYPE] == FIXED_TARIFF
        assert import_input[FIXED_TARIFF] == 0.42

    async def test_delete_leftover_entities(self, hass, setup_battery, caplog):
        entry, _handle = await setup_battery()
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        )
        stale = entity_registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "test_battery - obsolete sensor",
            config_entry=entry,
            device_id=device.id,
        )

        result = await self._start_options(hass, entry)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "delete_leftover_entities"}
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "init"

        assert entity_registry.async_get(stale.entity_id) is None
        assert "Deleted leftover Battery Sim entities" in caplog.text

    async def test_all_done_creates_options_entry(self, hass, setup_battery):
        entry, _handle = await setup_battery()
        result = await self._start_options(hass, entry)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "all_done"}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
