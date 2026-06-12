"""Tests for the battery_sim number platform."""
import pytest

from homeassistant.core import State

from custom_components.battery_sim.const import CONF_MINIMUM_USER_SELECTABLE_SOC

from pytest_homeassistant_custom_component.common import (
    mock_restore_cache_with_extra_data,
)

from .common import (
    CHARGE_LIMIT_NUMBER_ID,
    DISCHARGE_LIMIT_NUMBER_ID,
    MAXIMUM_SOC_NUMBER_ID,
    MINIMUM_SOC_NUMBER_ID,
    base_config,
)


def restore_data(entity_id, value, minimum=0.0, maximum=100.0, step=0.01, unit="kW"):
    """Build a RestoreNumber cache record."""
    return (
        State(entity_id, str(value)),
        {
            "native_max_value": maximum,
            "native_min_value": minimum,
            "native_step": step,
            "native_unit_of_measurement": unit,
            "native_value": value,
        },
    )


async def set_number(hass, entity_id, value):
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": value},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_sliders_created_with_expected_ranges(hass, setup_battery):
    await setup_battery()

    charge_limit = hass.states.get(CHARGE_LIMIT_NUMBER_ID)
    assert charge_limit.state == "4.0"
    assert charge_limit.attributes["max"] == 4.0
    assert charge_limit.attributes["min"] == 0.0

    discharge_limit = hass.states.get(DISCHARGE_LIMIT_NUMBER_ID)
    assert discharge_limit.state == "5.0"
    assert discharge_limit.attributes["max"] == 5.0

    minimum_soc = hass.states.get(MINIMUM_SOC_NUMBER_ID)
    assert minimum_soc.state == "0.0"
    assert minimum_soc.attributes["max"] == 100.0

    maximum_soc = hass.states.get(MAXIMUM_SOC_NUMBER_ID)
    # The slider is initialised with the integer 100, so no decimal is shown.
    assert maximum_soc.state == "100"


async def test_minimum_soc_slider_floor_from_config(hass, setup_battery):
    await setup_battery(base_config(**{CONF_MINIMUM_USER_SELECTABLE_SOC: 0.1}))

    minimum_soc = hass.states.get(MINIMUM_SOC_NUMBER_ID)
    assert minimum_soc.state == "10.0"
    assert minimum_soc.attributes["min"] == 10.0


async def test_setting_sliders_updates_handle(hass, setup_battery):
    _entry, handle = await setup_battery()

    await set_number(hass, CHARGE_LIMIT_NUMBER_ID, 2.5)
    assert handle._charge_limit == 2.5

    await set_number(hass, DISCHARGE_LIMIT_NUMBER_ID, 1.5)
    assert handle._discharge_limit == 1.5

    await set_number(hass, MINIMUM_SOC_NUMBER_ID, 20)
    assert handle._minimum_soc == 20

    await set_number(hass, MAXIMUM_SOC_NUMBER_ID, 80)
    assert handle._maximum_soc == 80


async def test_minimum_soc_clamped_to_configured_floor(hass, setup_battery):
    _entry, handle = await setup_battery(
        base_config(**{CONF_MINIMUM_USER_SELECTABLE_SOC: 0.1})
    )

    entity = hass.data["entity_components"]["number"].get_entity(
        MINIMUM_SOC_NUMBER_ID
    )
    await entity.async_set_native_value(5.0)
    await hass.async_block_till_done()

    assert handle._minimum_soc == 10.0
    assert hass.states.get(MINIMUM_SOC_NUMBER_ID).state == "10.0"


async def test_restore_slider_values(hass, setup_battery):
    mock_restore_cache_with_extra_data(
        hass,
        (
            restore_data(CHARGE_LIMIT_NUMBER_ID, 2.0, maximum=4.0),
            restore_data(DISCHARGE_LIMIT_NUMBER_ID, 1.0, maximum=5.0),
            restore_data(MAXIMUM_SOC_NUMBER_ID, 90.0, step=1, unit="%"),
        ),
    )
    _entry, handle = await setup_battery()

    assert handle._charge_limit == pytest.approx(2.0)
    assert handle._discharge_limit == pytest.approx(1.0)
    assert handle._maximum_soc == pytest.approx(90.0)
    assert hass.states.get(CHARGE_LIMIT_NUMBER_ID).state == "2.0"


async def test_restored_minimum_soc_clamped_to_floor(hass, setup_battery):
    mock_restore_cache_with_extra_data(
        hass,
        (restore_data(MINIMUM_SOC_NUMBER_ID, 5.0, step=1, unit="%"),),
    )
    _entry, handle = await setup_battery(
        base_config(**{CONF_MINIMUM_USER_SELECTABLE_SOC: 0.1})
    )

    assert handle._minimum_soc == pytest.approx(10.0)
    assert hass.states.get(MINIMUM_SOC_NUMBER_ID).state == "10.0"
