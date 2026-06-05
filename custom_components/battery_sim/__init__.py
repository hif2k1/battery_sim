"""Simulates a battery to evaluate how much energy it could save."""
import logging
import asyncio
from datetime import timedelta

import voluptuous as vol
import homeassistant.util.dt as dt_util

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.dispatcher import dispatcher_send, async_dispatcher_connect

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
)

from .const import (
    ATTR_ENERGY_BATTERY_IN,
    ATTR_ENERGY_BATTERY_OUT,
    ATTR_ENERGY_SAVED,
    ATTR_STATUS,
    ATTR_AVERAGE_ENERGY_VALUE,
    ATTR_MONEY_SAVED_EXPORT,
    ATTR_MONEY_SAVED_IMPORT,
    ATTR_MONEY_SAVED,
    ATTR_LAST_CHARGE_EFFICIENCY,
    ATTR_LAST_DISCHARGE_EFFICIENCY,
    BATTERY_DEGRADATION,
    BATTERY_CYCLES,
    BATTERY_MODE,
    BATTERY_PLATFORMS,
    CHARGE_ONLY,
    CHARGING_RATE,
    CONF_BATTERY_CHARGE_EFFICIENCY,
    CONF_BATTERY_DISCHARGE_EFFICIENCY,
    CONF_BATTERY_EFFICIENCY,
    CONF_BATTERY_MAX_CHARGE_RATE,
    CONF_BATTERY_MAX_DISCHARGE_RATE,
    CONF_BATTERY_SIZE,
    CONF_BATTERY,
    CONF_END_OF_LIFE_DEGRADATION,
    CONF_ENERGY_EXPORT_TARIFF,
    CONF_ENERGY_IMPORT_TARIFF,
    CONF_ENERGY_TARIFF,
    CONF_EXPORT_SENSOR,
    CONF_IMPORT_SENSOR,
    CONF_SOLAR_ENERGY_SENSOR,
    CONF_NOMINAL_INVERTER_POWER,
    CONF_UPDATE_FREQUENCY,
    CONF_MINIMUM_USER_SELECTABLE_SOC,
    DEFAULT_MINIMUM_USER_SELECTABLE_SOC,
    CONF_INPUT_LIST,
    CONF_RATED_BATTERY_CYCLES,
    DEFAULT_MODE,
    DISCHARGE_ONLY,
    DISCHARGING_RATE,
    DOMAIN,
    FORCE_DISCHARGE,
    MESSAGE_TYPE_BATTERY_UPDATE,
    MESSAGE_TYPE_GENERAL,
    MODE_CHARGING,
    MODE_DISCHARGING,
    MODE_EMPTY,
    MODE_FORCE_CHARGING,
    MODE_FORCE_DISCHARGING,
    MODE_FULL,
    MODE_IDLE,
    MINIMUM_UPDATE_INTERVAL_SECONDS,
    NO_TARIFF_INFO,
    OVERRIDE_CHARGING,
    PAUSE_BATTERY,
    FIXED_TARIFF,
    TARIFF_TYPE,
    SENSOR_ID,
    SENSOR_TYPE,
    TARIFF_SENSOR,
    IMPORT,
    EXPORT,
    SOLAR_POWER_CAP,
    SIMULATED_SENSOR,
)
from .helpers import (
    find_leftover_entity_registry_entries,
    generate_input_list,
    interpolate_efficiency,
    parse_efficiency_curve,
    validate_efficiency_config,
)

BATTERY_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_IMPORT_SENSOR): cv.entity_id,
            vol.Required(CONF_EXPORT_SENSOR): cv.entity_id,
            vol.Optional(CONF_SOLAR_ENERGY_SENSOR): cv.entity_id,
            vol.Optional(CONF_NOMINAL_INVERTER_POWER): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Optional(CONF_ENERGY_TARIFF): cv.entity_id,
            vol.Optional(CONF_ENERGY_EXPORT_TARIFF): cv.entity_id,
            vol.Optional(CONF_ENERGY_IMPORT_TARIFF): cv.entity_id,
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_BATTERY_SIZE): vol.All(float),
            vol.Required(CONF_BATTERY_MAX_DISCHARGE_RATE): vol.All(float),
            vol.Optional(CONF_BATTERY_MAX_CHARGE_RATE, default=1.0): vol.All(float),
            vol.Optional(CONF_BATTERY_DISCHARGE_EFFICIENCY): vol.Any(
                vol.Coerce(float), vol.All(cv.string, validate_efficiency_config)
            ),
            vol.Optional(CONF_BATTERY_CHARGE_EFFICIENCY): vol.Any(
                vol.Coerce(float), vol.All(cv.string, validate_efficiency_config)
            ),
            vol.Optional(CONF_BATTERY_EFFICIENCY, default=1.0): vol.Any(
                vol.Coerce(float), vol.All(cv.string, validate_efficiency_config)
            ),
            vol.Optional(CONF_RATED_BATTERY_CYCLES, default=6000): vol.All(
                vol.Coerce(float), vol.Range(min=1)
            ),
            vol.Optional(CONF_END_OF_LIFE_DEGRADATION, default=0.8): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=1)
            ),
            vol.Optional(CONF_UPDATE_FREQUENCY, default=60): vol.All(
                vol.Coerce(int), vol.Range(min=1)
            ),
            vol.Optional(
                CONF_MINIMUM_USER_SELECTABLE_SOC,
                default=DEFAULT_MINIMUM_USER_SELECTABLE_SOC,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: BATTERY_CONFIG_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

_LOGGER = logging.getLogger(__name__)
SERVICE_REGISTRATION_KEY = f"{DOMAIN}_services_registered"

INITIAL_SOC_RATIO = 0.5
INITIAL_CHARGE_PERCENTAGE = 50
DEFAULT_BATTERY_STATUS = "Normal"
DEFAULT_BATTERY_DEGRADATION = 1.0


async def async_setup(hass, config):
    """Set up battery platforms from a YAML."""
    hass.data.setdefault(DOMAIN, {})

    if config.get(DOMAIN) is None:
        return True

    for battery, conf in config.get(DOMAIN).items():
        _LOGGER.debug("Setup %s.%s", DOMAIN, battery)
        handle = SimulatedBatteryHandle(conf, hass)
        if battery in hass.data[DOMAIN]:
            _LOGGER.warning("Battery name not unique - not able to create.")
            continue
        hass.data[DOMAIN][battery] = handle

        for platform in BATTERY_PLATFORMS:
            hass.async_create_task(
                discovery.async_load_platform(
                    hass,
                    platform,
                    DOMAIN,
                    [{CONF_BATTERY: battery, CONF_NAME: conf.get(CONF_NAME, battery)}],
                    config,
                )
            )
    return True


async def async_setup_entry(hass, entry) -> bool:
    """Set up battery platforms from a Config Flow Entry."""
    hass.data.setdefault(DOMAIN, {})
    
    _LOGGER.debug("Setup %s.%s", DOMAIN, entry.data[CONF_NAME])

    handle = SimulatedBatteryHandle(entry.data, hass, entry.entry_id)
    hass.data[DOMAIN][entry.entry_id] = handle

    # Register service
    async def handle_set_charge(call):
        device_id = call.data.get("device_id")
        state = call.data.get("charge_state")
        _LOGGER.debug("Calling set_battery_charge_state with: %s", state)

        # Lookup the device to get the correct handle
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(device_id)
        if not device:
            _LOGGER.error("Device not found: %s", device_id)
            return

        # Match to correct handle by comparing identifiers
        for handle_entry in hass.data[DOMAIN].values():
            if handle_entry.matches_device_identifiers(device.identifiers):
                handle_entry.async_set_battery_charge_state(state)
                _LOGGER.debug("Battery charge updated for device %s", handle_entry._name)
                break
        else:
            _LOGGER.error("No handle matched for device_id: %s", device_id)

    async def handle_set_cycles(call):
        device_id = call.data.get("device_id")
        cycles = call.data.get("battery_cycles")
        _LOGGER.debug("Calling set_battery_cycles with: %s", cycles)

        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(device_id)
        if not device:
            _LOGGER.error("Device not found: %s", device_id)
            return

        for handle_entry in hass.data[DOMAIN].values():
            if handle_entry.matches_device_identifiers(device.identifiers):
                handle_entry.async_set_battery_cycles(cycles)
                _LOGGER.debug("Battery cycles updated for device %s", handle_entry._name)
                break
        else:
            _LOGGER.error("No handle matched for device_id: %s", device_id)

    async def handle_set_stored_energy_value(call):
        device_id = call.data.get("device_id")
        stored_energy_value = call.data.get("stored_energy_value")
        _LOGGER.debug("Calling set_stored_energy_value with: %s", stored_energy_value)

        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(device_id)
        if not device:
            _LOGGER.error("Device not found: %s", device_id)
            return

        for handle_entry in hass.data[DOMAIN].values():
            if handle_entry.matches_device_identifiers(device.identifiers):
                handle_entry.async_set_stored_energy_value(stored_energy_value)
                _LOGGER.debug(
                    "Stored energy value updated for device %s", handle_entry._name
                )
                break
        else:
            _LOGGER.error("No handle matched for device_id: %s", device_id)

    if not hass.data.get(SERVICE_REGISTRATION_KEY):
        hass.services.async_register(
            DOMAIN,
            "set_battery_charge_state",
            handle_set_charge,
            schema=vol.Schema({
                vol.Required("device_id"): str,
                vol.Required("charge_state"): vol.All(vol.Coerce(float), vol.Range(min=0))
            }),
        )

        hass.services.async_register(
            DOMAIN,
            "set_battery_cycles",
            handle_set_cycles,
            schema=vol.Schema({
                vol.Required("device_id"): str,
                vol.Required("battery_cycles"): vol.All(vol.Coerce(float), vol.Range(min=0))
            }),
        )

        hass.services.async_register(
            DOMAIN,
            "set_stored_energy_value",
            handle_set_stored_energy_value,
            schema=vol.Schema({
                vol.Required("device_id"): str,
                vol.Required("stored_energy_value"): vol.Coerce(float)
            }),
        )
        hass.data[SERVICE_REGISTRATION_KEY] = True

    handle._listeners.append(entry.add_update_listener(async_update_settings))

    _log_leftover_entity_registry_entries(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, BATTERY_PLATFORMS)

    return True


def _log_leftover_entity_registry_entries(hass, entry):
    """Log stale entity registry entries for a battery config entry."""
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    leftovers = find_leftover_entity_registry_entries(
        entity_reg, device_reg, entry.data, entry.entry_id
    )
    if not leftovers:
        return

    _LOGGER.warning(
        "Battery Sim '%s' has leftover entities that are no longer used by the "
        "current settings: %s. Use the options flow item 'Delete leftover "
        "entities' to remove them.",
        entry.data[CONF_NAME],
        ", ".join(entry.entity_id for entry in leftovers),
    )


async def async_update_settings(hass, entry):
    _LOGGER.warning(f"Config change detected {entry.data[CONF_NAME]}")
    _log_leftover_entity_registry_entries(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)
    return


async def async_unload_entry(hass, config_entry):
    """Unload a config entry"""
    # Unload a config entry
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in BATTERY_PLATFORMS
            ]
        )
    )

    """Remove listeners"""
    handle = hass.data[DOMAIN][config_entry.entry_id]
    for listener in handle._listeners:
        if listener is not None:
            outcome = listener()
            _LOGGER.warning(f"unloading listener: {outcome}")
    if handle._pending_update_cancel is not None:
        handle._pending_update_cancel()
        handle._pending_update_cancel = None

    _LOGGER.debug("Unload integration")
    if unload_ok:
        if DOMAIN in hass.data:
            hass.data[DOMAIN].pop(config_entry.entry_id, None)
        if DOMAIN in hass.data and not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "set_battery_charge_state")
            hass.services.async_remove(DOMAIN, "set_battery_cycles")
            hass.services.async_remove(DOMAIN, "set_stored_energy_value")
            hass.data.pop(SERVICE_REGISTRATION_KEY, None)
            hass.data.pop(DOMAIN, None)

    return unload_ok


class SimulatedBatteryHandle:
    """Representation of the battery itself."""

    @staticmethod
    def _safe_curve_efficiency(curve, fallback=1.0):
        """Return first efficiency value from a curve, or fallback when unavailable."""
        if curve and isinstance(curve[0], (list, tuple)) and len(curve[0]) > 1:
            return curve[0][1]
        return fallback

    def __init__(self, config, hass, entry_id=None):
        """Initialize the Battery."""
        self._hass = hass
        self._entry_id = entry_id
        self._date_recording_started = dt_util.now().isoformat()
        self._name = config[CONF_NAME]
        self._sensor_collection: list = []
        self._charging: bool = False
        self._accumulated_import_reading: float = 0.0
        self._last_battery_update_time = dt_util.utcnow().timestamp()
        # Periodic update cadence (seconds). Falls back to 60 for backwards compatibility.
        self._update_frequency = config.get(CONF_UPDATE_FREQUENCY, 60)
        self._max_discharge: float = 0.0
        # Monetary book value of the energy currently held in the simulated battery.
        # This is tracked separately from published savings counters.
        self._stored_energy_value: float = 0.0
        self._pending_restored_average_energy_value: float | None = None
        self._battery_charge_state_restore_complete: bool = False

        self._charge_limit = config[CONF_BATTERY_MAX_CHARGE_RATE]
        self._discharge_limit = config[CONF_BATTERY_MAX_DISCHARGE_RATE]
        self._minimum_user_selectable_soc: float = min(
            max(
                float(
                    config.get(
                        CONF_MINIMUM_USER_SELECTABLE_SOC,
                        DEFAULT_MINIMUM_USER_SELECTABLE_SOC,
                    )
                ),
                0.0,
            ),
            1.0,
        )
        self._minimum_soc: float = self.minimum_user_selectable_soc_percentage
        self._maximum_soc: float = 100
        self._charge_percentage: float = INITIAL_CHARGE_PERCENTAGE
        self._charge_state: float = config[CONF_BATTERY_SIZE] * INITIAL_SOC_RATIO
        self._accumulated_export_reading: float = 0.0
        self._accumulated_solar_reading: float = 0.0
        self._last_import_reading_sensor_data = None
        self._last_export_reading_sensor_data = None
        self._energy_saved_today: float = 0.0
        self._energy_saved_week: float = 0.0
        self._energy_saved_month: float = 0.0
        self._solar_entity_id = config.get(CONF_SOLAR_ENERGY_SENSOR)
        self._nominal_inverter_power = config.get(CONF_NOMINAL_INVERTER_POWER)
        self._listeners = []
        self._pending_update_cancel = None

        self._battery_size = config[CONF_BATTERY_SIZE]
        self._rated_battery_cycles = config.get(CONF_RATED_BATTERY_CYCLES, 6000.0)
        self._end_of_life_degradation = config.get(CONF_END_OF_LIFE_DEGRADATION, 0.8)
        if self._charge_state > self._battery_size:
            self._charge_state = self._battery_size
        self._max_discharge_rate = config[CONF_BATTERY_MAX_DISCHARGE_RATE]
        self._max_charge_rate = config[CONF_BATTERY_MAX_CHARGE_RATE]
        default_discharge_efficiency = config.get(CONF_BATTERY_EFFICIENCY, 1.0)
        self._battery_discharge_efficiency = config.get(
            CONF_BATTERY_DISCHARGE_EFFICIENCY, default_discharge_efficiency
        )
        self._battery_charge_efficiency = config.get(
            CONF_BATTERY_CHARGE_EFFICIENCY, default_discharge_efficiency
        )
        self._battery_discharge_efficiency_curve = parse_efficiency_curve(
            self._battery_discharge_efficiency
        )
        self._battery_charge_efficiency_curve = parse_efficiency_curve(
            self._battery_charge_efficiency
        )
        if CONF_INPUT_LIST in config:
            self._inputs = config[CONF_INPUT_LIST]
        else:
            """Needed for backwards compatability"""
            self._inputs = generate_input_list(config=config)

        self._switches: dict = {
            PAUSE_BATTERY: False,
        }
        self._battery_mode = DEFAULT_MODE

        default_charge_efficiency = self._safe_curve_efficiency(
            self._battery_charge_efficiency_curve
        )
        default_discharge_efficiency = self._safe_curve_efficiency(
            self._battery_discharge_efficiency_curve
        )
        self._sensors: dict = {
            ATTR_ENERGY_SAVED: 0.0,
            ATTR_ENERGY_BATTERY_OUT: 0.0,
            ATTR_ENERGY_BATTERY_IN: 0.0,
            CHARGING_RATE: 0.0,
            DISCHARGING_RATE: 0.0,
            SOLAR_POWER_CAP: 0.0,
            ATTR_MONEY_SAVED: 0.0,
            ATTR_AVERAGE_ENERGY_VALUE: 0.0,
            BATTERY_MODE: MODE_IDLE,
            ATTR_STATUS: DEFAULT_BATTERY_STATUS,
            ATTR_MONEY_SAVED_IMPORT: 0.0,
            ATTR_MONEY_SAVED_EXPORT: 0.0,
            BATTERY_CYCLES: 0.0,
            BATTERY_DEGRADATION: DEFAULT_BATTERY_DEGRADATION,
            ATTR_LAST_CHARGE_EFFICIENCY: default_charge_efficiency,
            ATTR_LAST_DISCHARGE_EFFICIENCY: default_discharge_efficiency,
        }
        for input_details in self._inputs:
            self._sensors[input_details[SIMULATED_SENSOR]] = 0.0

        async_at_start(self._hass, self.async_source_tracking)

        self._listeners.append(
            async_dispatcher_connect(
                self._hass,
                f"{self._name}-{MESSAGE_TYPE_GENERAL}",
                self.async_reset_battery,
            )
        )

    @property
    def device_identifier(self):
        """Return a stable identifier tuple used for device registry linking."""
        return (DOMAIN, self._entry_id or self._name)

    def matches_device_identifiers(self, identifiers):
        """Return true when any known identifier matches this handle."""
        known_identifiers = {
            self.device_identifier,
            (DOMAIN, self._name),  # Backward compatibility for existing devices.
        }
        return bool(known_identifiers.intersection(identifiers))

    def _minimum_user_selectable_energy(
        self, max_capacity: float | None = None
    ) -> float:
        """Return the physical, never-dischargeable energy floor in kWh."""
        if max_capacity is None:
            max_capacity = self.current_max_capacity
        return max(
            max(float(max_capacity), 0.0)
            * float(self._minimum_user_selectable_soc),
            0.0,
        )

    def _value_accounting_energy(
        self,
        charge_state: float | None = None,
        max_capacity: float | None = None,
    ) -> float:
        """Return the energy that participates in stored-value accounting.

        The energy below CONF_MINIMUM_USER_SELECTABLE_SOC is a physical floor: it
        cannot be selected for discharge and should not dilute the reported
        average value of the energy that can actually be used.

        The maximum capacity is an explicit argument so callers that rescale
        across ageing/degradation changes can compare the old charge against
        the old floor and the new charge against the new floor.
        """
        if charge_state is None:
            charge_state = self._charge_state
        return max(
            max(float(charge_state), 0.0)
            - self._minimum_user_selectable_energy(max_capacity),
            0.0,
        )

    @property
    def non_dischargeable_capacity(self) -> float:
        """Return the reserved energy (kWh) that can never be discharged."""
        return self._minimum_user_selectable_energy()

    @property
    def dischargeable_stored_energy(self) -> float:
        """Return the stored energy (kWh) currently above the reserve floor."""
        return self._value_accounting_energy()

    def _update_average_energy_value_sensor(self) -> None:
        """Publish the average monetary value per usable kWh currently stored."""
        value_accounting_energy = self._value_accounting_energy()
        if value_accounting_energy <= 0.000001:
            self._stored_energy_value = 0.0
            self._sensors[ATTR_AVERAGE_ENERGY_VALUE] = 0.0
            return

        self._sensors[ATTR_AVERAGE_ENERGY_VALUE] = (
            self._stored_energy_value / value_accounting_energy
        )

    def _finalize_average_energy_value_restore(self) -> None:
        """Finalize stored-value restoration after battery SoC is available."""
        if not self._battery_charge_state_restore_complete:
            return

        if self._pending_restored_average_energy_value is not None:
            value_accounting_energy = self._value_accounting_energy()
            self._stored_energy_value = (
                self._pending_restored_average_energy_value * value_accounting_energy
                if value_accounting_energy > 0.000001
                else 0.0
            )
            self._pending_restored_average_energy_value = None

        self._update_average_energy_value_sensor()

    def _rescale_stored_energy_value_for_charge_state_change(
        self,
        previous_charge_state: float,
        new_charge_state: float,
        previous_max_capacity: float | None = None,
        new_max_capacity: float | None = None,
    ) -> None:
        """Preserve average stored-energy value across external SoC adjustments.

        This helper is used only when stored energy changes outside the normal
        charge/discharge value-accounting path, such as a manual SoC change,
        degradation-driven capacity clipping, or a cycle-count update that
        reduces usable capacity.

        The average value is tracked per unit of energy above the configured
        physical floor. When maximum capacity changes, the physical floor moves
        with it, so callers may pass the old and new capacities explicitly.
        """
        previous_value_accounting_energy = self._value_accounting_energy(
            previous_charge_state, previous_max_capacity
        )
        new_value_accounting_energy = self._value_accounting_energy(
            new_charge_state, new_max_capacity
        )

        if new_value_accounting_energy <= 0.000001:
            self._stored_energy_value = 0.0
        elif previous_value_accounting_energy > 0.000001:
            self._stored_energy_value *= (
                new_value_accounting_energy / previous_value_accounting_energy
            )
        else:
            # There is no existing priced usable energy to preserve when the
            # battery changes from below the physical floor to above it through
            # an external SoC adjustment. Treat the newly introduced usable
            # energy as unvalued.
            self._stored_energy_value = 0.0

        self._update_average_energy_value_sensor()

    def async_set_battery_charge_state(self, state: float):
        """Set the battery state of charge while preserving its average energy value."""
        _LOGGER.debug("Set battery charge state")

        previous_charge_state = max(float(self._charge_state), 0.0)
        if state <= 0:
            self._charge_state = 0.0
        elif state <= self.current_max_capacity:
            self._charge_state = state
        else:
            self._charge_state = self.current_max_capacity

        new_charge_state = max(float(self._charge_state), 0.0)
        self._rescale_stored_energy_value_for_charge_state_change(
            previous_charge_state,
            new_charge_state,
        )
        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")
        return

    def async_set_stored_energy_value(self, stored_energy_value: float):
        """Set the current monetary book value of the energy stored in the battery."""
        _LOGGER.debug("Set stored energy value")
        self._stored_energy_value = float(stored_energy_value)
        self._update_average_energy_value_sensor()
        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")
        return

    def async_set_battery_cycles(self, cycles: float):
        """Set battery cycles to simulate ageing on demand."""
        previous_charge_state = max(float(self._charge_state), 0.0)
        previous_max_capacity = self.current_max_capacity
        self._sensors[BATTERY_CYCLES] = max(float(cycles), 0.0)
        self._sensors[ATTR_ENERGY_BATTERY_IN] = self._sensors[BATTERY_CYCLES] * float(
            self._battery_size
        )
        self._sensors[BATTERY_DEGRADATION] = self.degradation_factor
        self._charge_state = min(float(self._charge_state), self.current_max_capacity)
        new_charge_state = max(float(self._charge_state), 0.0)
        self._rescale_stored_energy_value_for_charge_state_change(
            previous_charge_state,
            new_charge_state,
            previous_max_capacity,
            self.current_max_capacity,
        )
        self._charge_percentage = round(100 * self._charge_state / self.current_max_capacity)

        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")
        return

    def async_reset_battery(self):
        """Reset the battery to start over."""
        _LOGGER.debug("Reset battery")
        for input in self._inputs:
            self.reset_sim_sensor(input[SIMULATED_SENSOR])

        self._charge_state = self.current_max_capacity * INITIAL_SOC_RATIO
        self._charge_percentage = INITIAL_CHARGE_PERCENTAGE

        default_charge_efficiency = self._safe_curve_efficiency(
            self._battery_charge_efficiency_curve
        )
        default_discharge_efficiency = self._safe_curve_efficiency(
            self._battery_discharge_efficiency_curve
        )

        self._sensors[ATTR_ENERGY_SAVED] = 0.0
        self._sensors[ATTR_MONEY_SAVED] = 0.0
        self._stored_energy_value = 0.0
        self._sensors[ATTR_AVERAGE_ENERGY_VALUE] = 0.0
        self._sensors[ATTR_ENERGY_BATTERY_OUT] = 0.0
        self._sensors[ATTR_ENERGY_BATTERY_IN] = 0.0
        self._sensors[CHARGING_RATE] = 0.0
        self._sensors[DISCHARGING_RATE] = 0.0
        self._sensors[BATTERY_MODE] = MODE_IDLE
        self._sensors[ATTR_STATUS] = DEFAULT_BATTERY_STATUS
        self._sensors[ATTR_MONEY_SAVED_IMPORT] = 0.0
        self._sensors[ATTR_MONEY_SAVED_EXPORT] = 0.0
        self._sensors[BATTERY_CYCLES] = 0.0
        self._sensors[BATTERY_DEGRADATION] = DEFAULT_BATTERY_DEGRADATION
        self._sensors[ATTR_LAST_CHARGE_EFFICIENCY] = default_charge_efficiency
        self._sensors[ATTR_LAST_DISCHARGE_EFFICIENCY] = default_discharge_efficiency
        self._sensors[SOLAR_POWER_CAP] = 0.0
        self._accumulated_solar_reading = 0.0

        self._energy_saved_today = 0.0
        self._energy_saved_week = 0.0
        self._energy_saved_month = 0.0

        self._date_recording_started = dt_util.now().isoformat()
        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")
        return

    def reset_sim_sensor(self, target_sensor_key):
        """Reset the Simulated Sensor."""
        _LOGGER.debug(f"Reset {target_sensor_key} sim sensor")

        self._sensors[target_sensor_key] = 0.0

        for input_details in self._inputs:
            if input_details[SIMULATED_SENSOR] == target_sensor_key:
                _LOGGER.warning(input_details[SENSOR_ID])
                if self._hass.states.get(input_details[SENSOR_ID]).state not in [
                    STATE_UNAVAILABLE,
                    STATE_UNKNOWN,
                ]:
                    self._sensors[target_sensor_key] = float(
                        self._hass.states.get(input_details[SENSOR_ID]).state
                    )

        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")

    @callback
    def async_source_tracking(self, event):
        """Wait for source to be ready, then start."""

        for input_details in self._inputs:
            """Start tracking state changes for a sensor."""
            self._listeners.append(
                async_track_state_change_event(
                    self._hass, [input_details[SENSOR_ID]], self.async_reading_handler
                )
            )
        _LOGGER.debug(f"{self._name} monitoring {input_details[SENSOR_ID]}")

        # Track solar sensor if configured
        if self._solar_entity_id is not None:
            self._listeners.append(
                async_track_state_change_event(
                    self._hass, [self._solar_entity_id], self.async_solar_reading_handler
                )
            )
            _LOGGER.debug(f"{self._name} monitoring solar sensor {self._solar_entity_id}")

        # Also update on a fixed cadence so the battery reacts even when meters
        # publish infrequently or when only switches/controls change.
        self._listeners.append(
            async_track_time_interval(
                self._hass,
                self.async_periodic_update,
                timedelta(seconds=int(self._update_frequency)),
            )
        )
        return

    @callback
    def async_periodic_update(self, now):
        """Update battery on a fixed cadence using accumulated readings."""
        self._async_maybe_update_battery()

    @callback
    def async_reading_handler(
        self,
        event,
    ):
        sensor_id = event.data.get("entity_id")
        for input_details in self._inputs:
            if sensor_id == input_details[SENSOR_ID]:
                break
        else:
            _LOGGER.warning(
                f"Error reading input sensor {sensor_id} not found in input sensors"
            )
            return

        """Handle the sensor state changes for import or export."""
        sensor_charge_rate = (
            DISCHARGING_RATE if input_details[SENSOR_TYPE] == IMPORT else CHARGING_RATE
        )

        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if (
            old_state is None
            or sensor_id is None
            or new_state is None
            or old_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            or new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
        ):
            # Incorrect Setup or Sensors are not ready
            return

        units = self._hass.states.get(sensor_id).attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        )

        if units not in [UnitOfEnergy.KILO_WATT_HOUR, UnitOfEnergy.WATT_HOUR]:
            _LOGGER.warning(
                "(%s) Unsupported energy unit '%s' for sensor %s; expected kWh or Wh. Ignoring update.",
                self._name,
                units,
                sensor_id,
            )
            return

        conversion_factor = 1.0 if units == UnitOfEnergy.KILO_WATT_HOUR else 0.001
        unit_of_energy = "kWh" if units == UnitOfEnergy.KILO_WATT_HOUR else "Wh"

        new_state_value = float(new_state.state) * conversion_factor
        old_state_value = float(old_state.state) * conversion_factor

        if self._sensors[input_details[SIMULATED_SENSOR]] is None:
            self._sensors[input_details[SIMULATED_SENSOR]] = old_state_value

        if new_state_value == old_state_value:
            # _LOGGER.debug("(%s) No change in readings .. ", self._name)
            return

        reading_variance = new_state_value - old_state_value

        _LOGGER.debug(
            f"({self._name}) {sensor_id} {input_details[SENSOR_TYPE]}: {old_state_value} {unit_of_energy} => {new_state_value} {unit_of_energy} = Δ {reading_variance} {unit_of_energy}"
        )

        if reading_variance < 0:
            _LOGGER.debug(
                "(%s) %s sensor value decreased - rebasing simulated sensor %s",
                self._name,
                input_details[SENSOR_TYPE],
                input_details[SIMULATED_SENSOR],
            )
            self._sensors[sensor_charge_rate] = 0
            self._sensors[input_details[SIMULATED_SENSOR]] = new_state_value
            dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")
            return

        if input_details[SENSOR_TYPE] == IMPORT:
            self._last_import_reading_sensor_data = input_details
            self._accumulated_import_reading += reading_variance

        if input_details[SENSOR_TYPE] == EXPORT:
            self._last_export_reading_sensor_data = input_details
            self._accumulated_export_reading += reading_variance

        # NOTE: battery updates are handled by async_periodic_update().
        return

    @callback
    def async_solar_reading_handler(self, event):
        """Handle state changes for solar energy sensor."""
        sensor_id = event.data.get("entity_id")
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if (
            old_state is None
            or sensor_id is None
            or new_state is None
            or old_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
            or new_state.state in [STATE_UNKNOWN, STATE_UNAVAILABLE]
        ):
            # Sensor not ready
            return

        units = self._hass.states.get(sensor_id).attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        )

        if units in [UnitOfEnergy.KILO_WATT_HOUR, UnitOfEnergy.WATT_HOUR]:
            conversion_factor = 1.0 if units == UnitOfEnergy.KILO_WATT_HOUR else 0.001
            unit_of_energy = "kWh" if units == UnitOfEnergy.KILO_WATT_HOUR else "Wh"
        else:
            return

        new_state_value = float(new_state.state) * conversion_factor
        old_state_value = float(old_state.state) * conversion_factor

        if new_state_value == old_state_value:
            return

        reading_variance = new_state_value - old_state_value

        _LOGGER.debug(
            f"({self._name}) Solar sensor {sensor_id}: {old_state_value} {unit_of_energy} => {new_state_value} {unit_of_energy} = Δ {reading_variance} {unit_of_energy}"
        )

        if reading_variance < 0:
            _LOGGER.debug(
                "(%s) Solar sensor value decreased - meter may have been reset",
                self._name,
            )
            self._accumulated_solar_reading = 0
            return

        self._accumulated_solar_reading += reading_variance

        # NOTE: battery updates are handled by async_periodic_update().
        return

    def get_tariff_information(self, input_details):
        if input_details is None:
            return None
        """Get Tarrif information to be used for calculating."""
        if input_details[TARIFF_TYPE] == NO_TARIFF_INFO:
            return None
        elif input_details[TARIFF_TYPE] == FIXED_TARIFF:
            return input_details[FIXED_TARIFF]

        # Default behavior - assume sensor entities
        if (
            TARIFF_SENSOR not in input_details
            or input_details[TARIFF_SENSOR] is None
            or len(input_details[TARIFF_SENSOR]) < 6
            or self._hass.states.get(input_details[TARIFF_SENSOR]) is None
            or self._hass.states.get(input_details[TARIFF_SENSOR]).state
            in [STATE_UNAVAILABLE, STATE_UNKNOWN]
        ):
            return None

        return float(self._hass.states.get(input_details[TARIFF_SENSOR]).state)

    def set_slider_limit(self, value: float, key: str):
        """Called by slider to update internal charge limit."""
        if key == "charge_limit":        
            self._charge_limit = value
        elif key == "discharge_limit":        
            self._discharge_limit = value
        elif key == "minimum_soc":        
            self._minimum_soc = max(
                float(value), self.minimum_user_selectable_soc_percentage
            )
        elif key == "maximum_soc":        
            self._maximum_soc = value
        else:
            _LOGGER.error("Unknown slider type in __init__.py")

    @callback
    def async_trigger_update(self):
        """Apply pending readings and current controls immediately."""
        self._async_maybe_update_battery()

    def _async_maybe_update_battery(self):
        """Apply pending readings once the minimum update interval has elapsed."""
        elapsed_seconds = dt_util.utcnow().timestamp() - self._last_battery_update_time
        if elapsed_seconds < MINIMUM_UPDATE_INTERVAL_SECONDS:
            delay = MINIMUM_UPDATE_INTERVAL_SECONDS - elapsed_seconds
            if self._pending_update_cancel is None:
                _LOGGER.debug(
                    "(%s) Delaying battery update by %.3f seconds to satisfy minimum interval.",
                    self._name,
                    delay,
                )
                self._pending_update_cancel = async_call_later(
                    self._hass, delay, self._async_delayed_update
                )
            return

        if self._pending_update_cancel is not None:
            self._pending_update_cancel()
            self._pending_update_cancel = None

        self.update_battery(
            self._accumulated_import_reading,
            self._accumulated_export_reading,
            self._accumulated_solar_reading,
        )
        self._accumulated_export_reading = 0.0
        self._accumulated_import_reading = 0.0
        self._accumulated_solar_reading = 0.0

    @callback
    def _async_delayed_update(self, _now):
        """Run a delayed update created to enforce the minimum update interval."""
        self._pending_update_cancel = None
        self._async_maybe_update_battery()

    @property
    def degradation_factor(self) -> float:
        """Return current degradation factor based on charge/discharge cycles."""
        cycles = float(self._sensors.get(BATTERY_CYCLES, 0.0))
        capped_progress = min(max(cycles / float(self._rated_battery_cycles), 0.0), 1.0)
        return 1.0 - ((1.0 - float(self._end_of_life_degradation)) * capped_progress)

    @property
    def current_max_capacity(self) -> float:
        """Return current degraded maximum battery capacity in kWh."""
        return max(float(self._battery_size) * self.degradation_factor, 0.000001)

    @property
    def minimum_user_selectable_soc_percentage(self) -> float:
        """Return the configured minimum selectable SOC as a percentage."""
        return 100.0 * float(self._minimum_user_selectable_soc)

    def update_battery(self, import_amount, export_amount, solar_amount=0.0):
        """Update battery statistics based on the reading for Im- or Export."""
        amount_to_charge: float = 0.0
        amount_to_discharge: float = 0.0
        net_export: float = 0.0
        net_import: float = 0.0

        if self._charge_state == "unknown":
            self._charge_state = 0.0
        charge_state_before_update = max(float(self._charge_state), 0.0)

        """
            Calculate maximum possible charge and discharge based on battery
            specifications and time since last discharge
        """
        time_now = dt_util.utcnow().timestamp()
        time_last_update = self._last_battery_update_time
        time_since_last_battery_update = time_now - time_last_update

        _LOGGER.debug(
            "(%s), Size: (%s)kWh, Import: (%s), Export: (%s), Initial charge level: (%s) .... Timings: %s = Now / %s = Last Update / %s Time (sec).",
            self._name,
            self._battery_size,
            import_amount,
            export_amount,
            self._charge_state,
            time_now,
            time_last_update,
            time_since_last_battery_update,
        )

        max_discharge = time_since_last_battery_update * (
            self._max_discharge_rate / 3600
        )
        max_charge = time_since_last_battery_update * (self._max_charge_rate / 3600)
        interval_hours = max(time_since_last_battery_update / 3600, 1 / 3600)
        charge_limit = time_since_last_battery_update * (self._charge_limit / 3600)
        discharge_limit = time_since_last_battery_update * (self._discharge_limit / 3600)

        if self._solar_entity_id is not None:
            solar_cap = max(float(solar_amount), 0.0)
            max_charge = min(max_charge, solar_cap)
            self._sensors[SOLAR_POWER_CAP] = solar_cap / interval_hours
            if self._nominal_inverter_power is not None:
                available_inverter_discharge_power = max(
                    float(self._nominal_inverter_power) - self._sensors[SOLAR_POWER_CAP],
                    0.0,
                )
                max_discharge = min(
                    max_discharge, available_inverter_discharge_power * interval_hours
                )
            _LOGGER.debug(
                f"({self._name}) Solar cap: {solar_cap} kWh over {interval_hours:.4f} hours = {self._sensors[SOLAR_POWER_CAP]:.3f} kW"
            )
        else:
            self._sensors[SOLAR_POWER_CAP] = 0.0

        effective_max_capacity = self.current_max_capacity
        max_charge_soc_capacity = effective_max_capacity * float(self._maximum_soc) / 100
        min_discharge_soc_capacity = (
            effective_max_capacity * float(self._minimum_soc) / 100
        )

        available_capacity_to_charge = max(
            max_charge_soc_capacity - float(self._charge_state), 0
        )
        available_capacity_to_discharge = max(
            float(self._charge_state) - min_discharge_soc_capacity, 0
        )
        
        if self._switches[PAUSE_BATTERY] or self._battery_mode == PAUSE_BATTERY:
            _LOGGER.debug("(%s) Battery paused.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = 0.0

        elif self._battery_mode == OVERRIDE_CHARGING:
            _LOGGER.debug("(%s) Battery override charging.", self._name)
            amount_to_charge = min(max_charge, charge_limit)
            amount_to_discharge = 0.0
            self._charging = True

        elif self._battery_mode == FORCE_DISCHARGE:
            _LOGGER.debug("(%s) Battery forced discharging.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = min(max_discharge, discharge_limit)

        elif self._battery_mode == CHARGE_ONLY:
            _LOGGER.debug("(%s) Battery charge only mode.", self._name)
            amount_to_charge = min(export_amount, max_charge, charge_limit)
            amount_to_discharge = 0.0

        elif self._battery_mode == DISCHARGE_ONLY:
            _LOGGER.debug("(%s) Battery discharge only mode.", self._name)
            amount_to_charge = 0.0
            amount_to_discharge = min(import_amount, max_discharge, discharge_limit)

        else:
            _LOGGER.debug("(%s) Battery normal mode.", self._name)

            amount_to_charge = min(export_amount, max_charge, charge_limit)
            amount_to_discharge = min(import_amount, max_discharge, discharge_limit)

        # Keep amount_to_charge as input-side energy and amount_to_discharge as
        # output-side delivered energy. The SoC capacities are battery-internal,
        # so convert those limits through the efficiency curve. Because the
        # efficiency curve is power-dependent, recompute it after each clipping
        # step until the clipped amount and efficiency agree.
        for _ in range(10):
            if amount_to_charge <= 0.0:
                break
            charge_efficiency = interpolate_efficiency(
                self._battery_charge_efficiency_curve,
                amount_to_charge / interval_hours,
            )
            clipped_amount_to_charge = min(
                amount_to_charge,
                available_capacity_to_charge / max(charge_efficiency, 0.000001),
            )
            if abs(clipped_amount_to_charge - amount_to_charge) < 0.000001:
                break
            amount_to_charge = clipped_amount_to_charge

        for _ in range(10):
            if amount_to_discharge <= 0.0:
                break
            discharge_efficiency = interpolate_efficiency(
                self._battery_discharge_efficiency_curve,
                amount_to_discharge / interval_hours,
            )
            clipped_amount_to_discharge = min(
                amount_to_discharge,
                available_capacity_to_discharge * discharge_efficiency,
            )
            if abs(clipped_amount_to_discharge - amount_to_discharge) < 0.000001:
                break
            amount_to_discharge = clipped_amount_to_discharge

        requested_charge_power = (
            amount_to_charge / interval_hours if amount_to_charge > 0 else 0.0
        )
        requested_discharge_power = (
            amount_to_discharge / interval_hours if amount_to_discharge > 0 else 0.0
        )
        charge_efficiency = interpolate_efficiency(
            self._battery_charge_efficiency_curve, requested_charge_power
        )
        discharge_efficiency = interpolate_efficiency(
            self._battery_discharge_efficiency_curve, requested_discharge_power
        )
        self._sensors[ATTR_LAST_CHARGE_EFFICIENCY] = (
            charge_efficiency if amount_to_charge > 0 else None
        )
        self._sensors[ATTR_LAST_DISCHARGE_EFFICIENCY] = (
            discharge_efficiency if amount_to_discharge > 0 else None
        )

        if self._switches[PAUSE_BATTERY] or self._battery_mode == PAUSE_BATTERY:
            self._sensors[BATTERY_MODE] = MODE_IDLE
        elif self._battery_mode == OVERRIDE_CHARGING:
            self._sensors[BATTERY_MODE] = (
                MODE_FORCE_CHARGING if amount_to_charge > 0.0 else MODE_IDLE
            )
        elif self._battery_mode == FORCE_DISCHARGE:
            self._sensors[BATTERY_MODE] = (
                MODE_FORCE_DISCHARGING if amount_to_discharge > 0.0 else MODE_IDLE
            )
        elif amount_to_charge > 0.0 and amount_to_charge >= amount_to_discharge:
            self._sensors[BATTERY_MODE] = MODE_CHARGING
        elif amount_to_discharge > 0.0:
            self._sensors[BATTERY_MODE] = MODE_DISCHARGING
        else:
            self._sensors[BATTERY_MODE] = MODE_IDLE

        # Calculate net grid import/export once, using efficiency-adjusted
        # charge/discharge amounts.
        if self._battery_mode == OVERRIDE_CHARGING:
            net_export = max(export_amount - amount_to_charge, 0)
            net_import = max(amount_to_charge - export_amount, 0) + import_amount
        elif self._battery_mode == FORCE_DISCHARGE:
            net_export = max(amount_to_discharge - import_amount, 0) + export_amount
            net_import = max(import_amount - amount_to_discharge, 0)
        elif self._battery_mode == CHARGE_ONLY:
            net_import = import_amount
            net_export = export_amount - amount_to_charge
        elif self._battery_mode == DISCHARGE_ONLY:
            net_import = import_amount - amount_to_discharge
            net_export = export_amount
        elif self._switches[PAUSE_BATTERY] or self._battery_mode == PAUSE_BATTERY:
            net_export = export_amount
            net_import = import_amount
        else:
            net_import = import_amount - amount_to_discharge
            net_export = export_amount - amount_to_charge

        current_import_tariff = self.get_tariff_information(
            self._last_import_reading_sensor_data
        )
        current_export_tariff = self.get_tariff_information(
            self._last_export_reading_sensor_data
        )

        if current_import_tariff is not None:
            self._sensors[ATTR_MONEY_SAVED_IMPORT] += (
                import_amount - net_import
            ) * current_import_tariff
        if current_export_tariff is not None:
            self._sensors[ATTR_MONEY_SAVED_EXPORT] += (
                net_export - export_amount
            ) * current_export_tariff
        self._sensors[ATTR_MONEY_SAVED] = (
            self._sensors[ATTR_MONEY_SAVED_IMPORT]
            + self._sensors[ATTR_MONEY_SAVED_EXPORT]
        )

        # Track the monetary book value of the energy currently stored. Charge
        # additions use the already-available tariff information: charging from
        # exported energy has the opportunity cost of foregone export revenue,
        # while grid-backed forced charging uses the import tariff.
        charge_value_increment = 0.0
        if amount_to_charge > 0.0:
            charge_from_export = min(amount_to_charge, max(export_amount, 0.0))
            charge_from_import = max(amount_to_charge - charge_from_export, 0.0)
            if current_export_tariff is not None:
                charge_value_increment += charge_from_export * current_export_tariff
            if current_import_tariff is not None:
                charge_value_increment += charge_from_import * current_import_tariff

        # Since normal battery operation never allows the charge state to fall
        # below the physical floor, any charged energy is added to the
        # dischargeable/value-accounting portion of the battery. The floor is
        # therefore excluded from the value basis used for discharge, but the
        # charge value itself does not need an additional floor-crossing
        # correction.
        charge_state_after_charge = (
            charge_state_before_update + (amount_to_charge * charge_efficiency)
        )
        value_accounting_energy_after_charge = self._value_accounting_energy(
            charge_state_after_charge
        )

        retained_value_fraction = 1.0
        if amount_to_discharge > 0.0 and value_accounting_energy_after_charge > 0.000001:
            # Follow the requested convention for this monetary sensor: value is
            # removed as if discharge were 100% efficient. This deliberately does
            # not apply the possibly load-dependent discharge efficiency.
            retained_value_fraction = max(
                1.0 - (amount_to_discharge / value_accounting_energy_after_charge),
                0.0,
            )

        self._stored_energy_value = (
            self._stored_energy_value + charge_value_increment
        ) * retained_value_fraction

        self._charge_state = (
            float(self._charge_state)
            + (amount_to_charge * charge_efficiency)
            - (amount_to_discharge / max(discharge_efficiency, 0.000001))
        )

        self._sensors[ATTR_ENERGY_SAVED] += import_amount - net_import

        if self._last_import_reading_sensor_data is not None:
            self._sensors[
                self._last_import_reading_sensor_data[SIMULATED_SENSOR]
            ] += net_import
        if self._last_export_reading_sensor_data is not None:
            self._sensors[
                self._last_export_reading_sensor_data[SIMULATED_SENSOR]
            ] += net_export

        self._sensors[ATTR_ENERGY_BATTERY_IN] += amount_to_charge
        self._sensors[ATTR_ENERGY_BATTERY_OUT] += amount_to_discharge

        self._sensors[CHARGING_RATE] = amount_to_charge / interval_hours
        self._sensors[DISCHARGING_RATE] = amount_to_discharge / interval_hours
        self._sensors[BATTERY_CYCLES] = (
            self._sensors[ATTR_ENERGY_BATTERY_IN] / self._battery_size
        )
        self._sensors[BATTERY_DEGRADATION] = self.degradation_factor

        charge_state_before_capacity_clip = float(self._charge_state)
        self._charge_state = min(charge_state_before_capacity_clip, effective_max_capacity)
        if self._charge_state < charge_state_before_capacity_clip:
            # If degradation/capacity clipping removes stored energy, keep the
            # average value stable by reducing the cumulative stored value in
            # the same proportion. Both charge states relate to the same
            # effective capacity, so the non-dischargeable reserve is unchanged.
            self._rescale_stored_energy_value_for_charge_state_change(
                charge_state_before_capacity_clip,
                self._charge_state,
                effective_max_capacity,
                effective_max_capacity,
            )
        else:
            self._update_average_energy_value_sensor()

        self._charge_percentage = round(100 * self._charge_state / effective_max_capacity)

        # Keep "mode" (how the battery operates) separate from capacity "status".
        if self._charge_percentage < 2:
            self._sensors[ATTR_STATUS] = MODE_EMPTY
        elif self._charge_percentage > 98:
            self._sensors[ATTR_STATUS] = MODE_FULL
        else:
            self._sensors[ATTR_STATUS] = "Normal"

        # Reset day/week/month counters using Home Assistant's configured timezone.
        now_local = dt_util.now()
        last_update_local = dt_util.as_local(
            dt_util.utc_from_timestamp(time_last_update)
        )
        if now_local.date() != last_update_local.date():
            self._energy_saved_today = 0
        if now_local.isocalendar()[:2] != last_update_local.isocalendar()[:2]:
            self._energy_saved_week = 0
        if (now_local.year, now_local.month) != (
            last_update_local.year,
            last_update_local.month,
        ):
            self._energy_saved_month = 0

        self._last_battery_update_time = time_now

        dispatcher_send(self._hass, f"{self._name}-{MESSAGE_TYPE_BATTERY_UPDATE}")

        _LOGGER.debug("(%s) Battery update complete. New Charge level: (%s)", self._name, self._charge_state)
