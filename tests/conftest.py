"""Fixtures for battery_sim tests."""
import pytest

from homeassistant.config_entries import ConfigEntryState

from custom_components.battery_sim import SimulatedBatteryHandle
from custom_components.battery_sim.const import DOMAIN

from pytest_homeassistant_custom_component.common import MockConfigEntry

from .common import base_config


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading the custom integration in all tests."""
    yield


@pytest.fixture(autouse=True)
async def cleanup_battery_sim(hass):
    """Unload config entries and release leftover listeners after each test."""
    yield

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Handles created outside config entries (YAML setup) keep their own
    # listeners and timers; release them so no timers linger after the test.
    domain_data = hass.data.get(DOMAIN)
    if isinstance(domain_data, dict):
        for key, handle in list(domain_data.items()):
            if not isinstance(handle, SimulatedBatteryHandle):
                continue
            release_handle(handle)
            domain_data.pop(key, None)
    await hass.async_block_till_done()


def release_handle(handle):
    """Cancel timers and unsubscribe all listeners owned by a battery handle."""
    if handle._pending_update_cancel is not None:
        handle._pending_update_cancel()
        handle._pending_update_cancel = None
    for unsub in handle._listeners:
        if unsub is not None:
            unsub()
    handle._listeners.clear()


@pytest.fixture
async def setup_battery(hass):
    """Return a factory that sets up a battery_sim config entry."""

    async def _setup(config=None, **entry_kwargs):
        data = config or base_config()
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=data,
            title=data["name"],
            **entry_kwargs,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry, hass.data[DOMAIN][entry.entry_id]

    return _setup


@pytest.fixture
async def make_handle(hass, freezer):
    """Return a factory creating bare battery handles with frozen time."""
    handles = []

    def _make(config=None):
        handle = SimulatedBatteryHandle(config or base_config(), hass)
        handles.append(handle)
        return handle

    yield _make

    for handle in handles:
        release_handle(handle)
