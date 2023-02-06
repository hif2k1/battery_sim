"""Simulates a battery to evaluate how much energy it could save."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BATTERY,
    CONF_BATTERY_EFFICIENCY,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_SIZE,
    CONF_ENERGY_TARIFF,
    CONF_IMPORT_SENSOR,
    CONF_EXPORT_SENSOR,
    DATA_UTILITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

BATTERY_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_IMPORT_SENSOR): cv.entity_id,
            vol.Required(CONF_EXPORT_SENSOR): cv.entity_id,
            vol.Optional(CONF_ENERGY_TARIFF): cv.entity_id,
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_BATTERY_SIZE): vol.All(float),
            vol.Required(CONF_BATTERY_MAX_DISCHARGE_RATE): vol.All(float),
            vol.Optional(CONF_BATTERY_MAX_CHARGE_RATE, default=1.0): vol.All(float),
            vol.Optional(CONF_BATTERY_EFFICIENCY, default=1.0): vol.All(float),
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: BATTERY_CONFIG_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

async def async_setup(hass, config):
    """Set up a battery"""
    hass.data[DATA_UTILITY] = {}

    for battery, conf in config.get(DOMAIN).items():
        _LOGGER.debug("Setup %s.%s", DOMAIN, battery)

        hass.data[DATA_UTILITY][battery] = conf

        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                SENSOR_DOMAIN,
                DOMAIN,
                [{CONF_BATTERY: battery, CONF_NAME: conf.get(CONF_NAME, battery)}],
                config,
            )
        )
    return True

