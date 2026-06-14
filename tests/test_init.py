"""Tests for battery_sim setup, unload and services."""
import pytest

from homeassistant.const import CONF_NAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.battery_sim.const import (
    CONF_BATTERY_EFFICIENCY,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_SIZE,
    CONF_EXPORT_SENSOR,
    CONF_IMPORT_SENSOR,
    DOMAIN,
)

from .common import BATTERY_NAME, base_config

SERVICES = (
    "set_battery_charge_state",
    "set_battery_cycles",
    "get_efficiency",
    "set_stored_energy_value",
)


def get_battery_device(hass, entry):
    """Return the device registry entry created for a battery config entry."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    return device


async def test_setup_entry_creates_handle_and_services(hass, setup_battery):
    entry, handle = await setup_battery()

    assert hass.data[DOMAIN][entry.entry_id] is handle
    assert handle.name == BATTERY_NAME
    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)


async def test_unload_entry_removes_handle_and_services(hass, setup_battery):
    entry, _handle = await setup_battery()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN not in hass.data
    for service in SERVICES:
        assert not hass.services.has_service(DOMAIN, service)


async def test_services_persist_until_last_entry_unloaded(hass, setup_battery):
    entry_one, _ = await setup_battery()
    second_config = base_config(**{CONF_NAME: "second_battery"})
    entry_two, _ = await setup_battery(second_config)

    assert await hass.config_entries.async_unload(entry_one.entry_id)
    await hass.async_block_till_done()
    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)

    assert await hass.config_entries.async_unload(entry_two.entry_id)
    await hass.async_block_till_done()
    for service in SERVICES:
        assert not hass.services.has_service(DOMAIN, service)


async def test_set_battery_charge_state_service(hass, setup_battery):
    entry, handle = await setup_battery()
    device = get_battery_device(hass, entry)

    await hass.services.async_call(
        DOMAIN,
        "set_battery_charge_state",
        {"device_id": device.id, "charge_state": 7.5},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert handle._charge_state == pytest.approx(7.5)


async def test_set_battery_charge_state_unknown_device(
    hass, setup_battery, caplog
):
    _entry, handle = await setup_battery()

    await hass.services.async_call(
        DOMAIN,
        "set_battery_charge_state",
        {"device_id": "no-such-device", "charge_state": 7.5},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert handle._charge_state == pytest.approx(5.0)
    assert "Device not found" in caplog.text


async def test_set_battery_charge_state_unmatched_device(
    hass, setup_battery, caplog
):
    entry, handle = await setup_battery()
    device_registry = dr.async_get(hass)
    unrelated = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("other_domain", "other_device")},
    )

    await hass.services.async_call(
        DOMAIN,
        "set_battery_charge_state",
        {"device_id": unrelated.id, "charge_state": 7.5},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert handle._charge_state == pytest.approx(5.0)
    assert "No handle matched" in caplog.text


async def test_set_battery_cycles_service(hass, setup_battery):
    entry, handle = await setup_battery()
    device = get_battery_device(hass, entry)

    await hass.services.async_call(
        DOMAIN,
        "set_battery_cycles",
        {"device_id": device.id, "battery_cycles": 3000},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert handle._sensors["battery_cycles"] == pytest.approx(3000.0)
    assert handle.current_max_capacity == pytest.approx(9.0)


async def test_set_stored_energy_value_service(hass, setup_battery):
    entry, handle = await setup_battery()
    device = get_battery_device(hass, entry)

    await hass.services.async_call(
        DOMAIN,
        "set_stored_energy_value",
        {"device_id": device.id, "stored_energy_value": 1.5},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert handle._stored_energy_value == pytest.approx(1.5)


async def test_get_efficiency_service(hass, setup_battery):
    entry, _handle = await setup_battery()
    device = get_battery_device(hass, entry)

    response = await hass.services.async_call(
        DOMAIN,
        "get_efficiency",
        {"device_id": device.id, "efficiency_type": "charge", "power_level": 2.0},
        blocking=True,
        return_response=True,
    )

    assert response["success"] is True
    assert response["battery"] == BATTERY_NAME
    assert response["efficiency"] == pytest.approx(0.8)


async def test_get_efficiency_service_discharge(hass, setup_battery):
    entry, _handle = await setup_battery()
    device = get_battery_device(hass, entry)

    response = await hass.services.async_call(
        DOMAIN,
        "get_efficiency",
        {"device_id": device.id, "efficiency_type": "discharge", "power_level": 1.0},
        blocking=True,
        return_response=True,
    )

    assert response["efficiency"] == pytest.approx(0.9)


async def test_get_efficiency_service_unknown_device(hass, setup_battery):
    await setup_battery()

    response = await hass.services.async_call(
        DOMAIN,
        "get_efficiency",
        {
            "device_id": "no-such-device",
            "efficiency_type": "charge",
            "power_level": 2.0,
        },
        blocking=True,
        return_response=True,
    )

    assert response["success"] is False
    assert "No simulated battery found" in response["error"]


async def test_yaml_setup_creates_handle_and_entities(hass):
    yaml_config = {
        DOMAIN: {
            "my_battery": {
                CONF_NAME: "my_battery",
                CONF_IMPORT_SENSOR: "sensor.yaml_import_energy",
                CONF_EXPORT_SENSOR: "sensor.yaml_export_energy",
                CONF_BATTERY_SIZE: 8.0,
                CONF_BATTERY_MAX_DISCHARGE_RATE: 3.0,
                CONF_BATTERY_MAX_CHARGE_RATE: 2.0,
                CONF_BATTERY_EFFICIENCY: 0.9,
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, yaml_config)
    await hass.async_block_till_done()

    handle = hass.data[DOMAIN]["my_battery"]
    assert handle.name == "my_battery"
    assert handle._battery_size == 8.0
    # Discovery created the platform entities.
    assert hass.states.get("sensor.my_battery") is not None
    assert hass.states.get("switch.my_battery_pause_battery") is not None
    assert hass.states.get("select.my_battery_battery_mode") is not None


async def test_yaml_setup_without_domain_config(hass):
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert hass.data[DOMAIN] == {}


async def test_leftover_entities_logged_on_setup(hass, setup_battery, caplog):
    entry, _handle = await setup_battery()
    entity_registry = er.async_get(hass)
    device = get_battery_device(hass, entry)
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{BATTERY_NAME} - obsolete sensor",
        config_entry=entry,
        device_id=device.id,
    )

    caplog.clear()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert "has leftover entities" in caplog.text
