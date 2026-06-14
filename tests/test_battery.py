"""Tests for the core simulated battery logic in SimulatedBatteryHandle."""
from datetime import timedelta

import pytest

from homeassistant.core import Event

from custom_components.battery_sim.const import (
    ATTR_AVERAGE_ENERGY_VALUE,
    ATTR_ENERGY_BATTERY_IN,
    ATTR_ENERGY_BATTERY_OUT,
    ATTR_ENERGY_SAVED,
    ATTR_LAST_CHARGE_EFFICIENCY,
    ATTR_LAST_DISCHARGE_EFFICIENCY,
    ATTR_MONEY_SAVED,
    ATTR_MONEY_SAVED_EXPORT,
    ATTR_MONEY_SAVED_IMPORT,
    ATTR_STATUS,
    BATTERY_CYCLES,
    BATTERY_DEGRADATION,
    BATTERY_MODE,
    CHARGE_ONLY,
    CHARGING_RATE,
    CONF_BATTERY_CHARGE_EFFICIENCY,
    CONF_BATTERY_DISCHARGE_EFFICIENCY,
    CONF_BATTERY_EFFICIENCY,
    CONF_END_OF_LIFE_DEGRADATION,
    CONF_EXPORT_SENSOR,
    CONF_IMPORT_SENSOR,
    CONF_INPUT_LIST,
    CONF_MINIMUM_USER_SELECTABLE_SOC,
    DISCHARGE_ONLY,
    DISCHARGING_RATE,
    FORCE_DISCHARGE,
    GRID_EXPORT_SIM,
    GRID_IMPORT_SIM,
    MODE_CHARGING,
    MODE_DISCHARGING,
    MODE_EMPTY,
    MODE_FORCE_CHARGING,
    MODE_FORCE_DISCHARGING,
    MODE_FULL,
    MODE_IDLE,
    NO_TARIFF_INFO,
    OVERRIDE_CHARGING,
    PAUSE_BATTERY,
    SOLAR_POWER_CAP,
    TARIFF_SENSOR,
    TARIFF_TYPE,
)

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .common import (
    EXPORT_SENSOR_ID,
    EXPORT_TARIFF,
    EXPORT_TARIFF_SENSOR_ID,
    IMPORT_SENSOR_ID,
    IMPORT_TARIFF,
    IMPORT_TARIFF_SENSOR_ID,
    KWH_ATTRIBUTES,
    SOLAR_SENSOR_ID,
    WH_ATTRIBUTES,
    base_config,
    config_with_fixed_tariffs,
    config_with_solar,
    config_with_tariff_sensors,
    link_meter_readings,
    rewind_last_update,
)

ONE_HOUR = 3600


def update_after(handle, seconds, import_amount, export_amount, solar=0.0):
    """Run a battery update pretending `seconds` have passed since the last."""
    rewind_last_update(handle, seconds)
    handle.update_battery(import_amount, export_amount, solar)


class TestNormalMode:
    """Battery behaviour in the default (self-consumption) mode."""

    def test_initial_state(self, make_handle):
        handle = make_handle()
        assert handle.name == "test_battery"
        assert handle._charge_state == 5.0
        assert handle._sensors[BATTERY_MODE] == MODE_IDLE
        assert handle._sensors[ATTR_STATUS] == "Normal"
        assert handle._sensors[ATTR_LAST_CHARGE_EFFICIENCY] == 0.8
        assert handle._sensors[ATTR_LAST_DISCHARGE_EFFICIENCY] == 0.9

    def test_charges_from_export(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 0.0, 2.0)

        assert handle._charge_state == pytest.approx(5.0 + 2.0 * 0.8)
        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(2.0)
        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == 0.0
        assert handle._sensors[CHARGING_RATE] == pytest.approx(2.0)
        assert handle._sensors[DISCHARGING_RATE] == 0.0
        assert handle._sensors[BATTERY_MODE] == MODE_CHARGING
        assert handle._sensors[ATTR_LAST_CHARGE_EFFICIENCY] == pytest.approx(0.8)
        assert handle._sensors[ATTR_LAST_DISCHARGE_EFFICIENCY] is None
        # All exported energy went into the battery.
        assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(0.0)
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(0.0)
        assert handle._sensors[BATTERY_CYCLES] == pytest.approx(0.2)
        assert handle._charge_percentage == 66

    def test_discharges_to_cover_import(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 2.0, 0.0)

        assert handle._charge_state == pytest.approx(5.0 - 2.0 / 0.9)
        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(2.0)
        assert handle._sensors[ATTR_ENERGY_SAVED] == pytest.approx(2.0)
        assert handle._sensors[DISCHARGING_RATE] == pytest.approx(2.0)
        assert handle._sensors[BATTERY_MODE] == MODE_DISCHARGING
        assert handle._sensors[ATTR_LAST_DISCHARGE_EFFICIENCY] == pytest.approx(0.9)
        assert handle._sensors[ATTR_LAST_CHARGE_EFFICIENCY] is None
        # All import was covered by the battery.
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(0.0)

    def test_charge_limited_by_max_charge_rate(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 0.0, 10.0)

        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(4.0)
        assert handle._charge_state == pytest.approx(5.0 + 4.0 * 0.8)
        # Excess export still leaves to the grid.
        assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(6.0)

    def test_discharge_limited_by_capacity_and_efficiency(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 10.0, 0.0)

        # Only 5 kWh stored: deliverable energy is 5 * 0.9 = 4.5 kWh.
        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(4.5)
        assert handle._charge_state == pytest.approx(0.0)
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(5.5)
        assert handle._sensors[ATTR_STATUS] == MODE_EMPTY

    def test_charge_clipped_when_nearly_full(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        handle._charge_state = 9.5
        update_after(handle, ONE_HOUR, 0.0, 2.0)

        # Remaining capacity 0.5 kWh divided by 0.8 charge efficiency.
        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(0.625)
        assert handle._charge_state == pytest.approx(10.0)
        assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(1.375)
        assert handle._sensors[ATTR_STATUS] == MODE_FULL

    def test_rate_limits_scale_with_interval(self, make_handle):
        handle = make_handle()
        update_after(handle, ONE_HOUR / 2, 0.0, 5.0)

        # Half an hour at 4 kW allows 2 kWh into the battery.
        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(2.0)
        assert handle._sensors[CHARGING_RATE] == pytest.approx(4.0)

    def test_simultaneous_import_and_export(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 1.0, 2.0)

        assert handle._charge_state == pytest.approx(5.0 + 2.0 * 0.8 - 1.0 / 0.9)
        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(2.0)
        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(1.0)
        assert handle._sensors[BATTERY_MODE] == MODE_CHARGING
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(0.0)
        assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(0.0)

    def test_unknown_charge_state_recovers_to_zero(self, make_handle):
        handle = make_handle()
        handle._charge_state = "unknown"
        update_after(handle, ONE_HOUR, 0.0, 0.0)

        assert handle._charge_state == pytest.approx(0.0)
        assert handle._sensors[BATTERY_MODE] == MODE_IDLE


class TestBatteryModes:
    """Behaviour of the user-selectable operating modes."""

    def test_pause_via_switch(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        handle._switches[PAUSE_BATTERY] = True
        update_after(handle, ONE_HOUR, 3.0, 2.0)

        assert handle._charge_state == pytest.approx(5.0)
        assert handle._sensors[BATTERY_MODE] == MODE_IDLE
        assert handle._sensors[ATTR_ENERGY_SAVED] == pytest.approx(0.0)
        # Grid flows pass through unchanged.
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(3.0)
        assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(2.0)
        assert handle._sensors[ATTR_LAST_CHARGE_EFFICIENCY] is None
        assert handle._sensors[ATTR_LAST_DISCHARGE_EFFICIENCY] is None

    def test_pause_via_mode_select(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        handle._battery_mode = PAUSE_BATTERY
        update_after(handle, ONE_HOUR, 3.0, 2.0)

        assert handle._charge_state == pytest.approx(5.0)
        assert handle._sensors[BATTERY_MODE] == MODE_IDLE

    def test_force_charge_draws_from_grid(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        handle._battery_mode = OVERRIDE_CHARGING
        update_after(handle, ONE_HOUR, 1.0, 0.0)

        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(4.0)
        assert handle._charge_state == pytest.approx(5.0 + 4.0 * 0.8)
        assert handle._sensors[BATTERY_MODE] == MODE_FORCE_CHARGING
        # House import plus the full battery charge come from the grid.
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(5.0)
        assert handle._sensors[ATTR_ENERGY_SAVED] == pytest.approx(-4.0)

    def test_force_charge_idle_when_full(self, make_handle):
        handle = make_handle()
        handle._battery_mode = OVERRIDE_CHARGING
        handle._charge_state = 10.0
        update_after(handle, ONE_HOUR, 0.0, 0.0)

        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(0.0)
        assert handle._sensors[BATTERY_MODE] == MODE_IDLE

    def test_force_discharge_exports_to_grid(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        handle._battery_mode = FORCE_DISCHARGE
        update_after(handle, ONE_HOUR, 1.0, 0.5)

        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(4.5)
        assert handle._charge_state == pytest.approx(0.0)
        assert handle._sensors[BATTERY_MODE] == MODE_FORCE_DISCHARGING
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(0.0)
        assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(4.0)
        assert handle._sensors[ATTR_STATUS] == MODE_EMPTY

    def test_force_discharge_idle_when_empty(self, make_handle):
        handle = make_handle()
        handle._battery_mode = FORCE_DISCHARGE
        handle._charge_state = 0.0
        update_after(handle, ONE_HOUR, 0.0, 0.0)

        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(0.0)
        assert handle._sensors[BATTERY_MODE] == MODE_IDLE

    def test_charge_only_mode_never_discharges(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        handle._battery_mode = CHARGE_ONLY
        update_after(handle, ONE_HOUR, 2.0, 1.0)

        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(1.0)
        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(0.0)
        assert handle._charge_state == pytest.approx(5.0 + 1.0 * 0.8)
        # Imports pass straight through to the grid.
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(2.0)
        assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(0.0)

    def test_discharge_only_mode_never_charges(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        handle._battery_mode = DISCHARGE_ONLY
        update_after(handle, ONE_HOUR, 2.0, 1.0)

        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(0.0)
        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(2.0)
        assert handle._charge_state == pytest.approx(5.0 - 2.0 / 0.9)
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(0.0)
        assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(1.0)


class TestSliderLimits:
    """Behaviour of the charge/discharge limit and SoC sliders."""

    def test_charge_limit_slider(self, make_handle):
        handle = make_handle()
        handle.set_slider_limit(1.0, "charge_limit")
        update_after(handle, ONE_HOUR, 0.0, 5.0)

        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(1.0)

    def test_discharge_limit_slider(self, make_handle):
        handle = make_handle()
        handle.set_slider_limit(0.5, "discharge_limit")
        update_after(handle, ONE_HOUR, 5.0, 0.0)

        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(0.5)

    def test_minimum_soc_limits_discharge(self, make_handle):
        handle = make_handle()
        handle.set_slider_limit(20.0, "minimum_soc")
        update_after(handle, ONE_HOUR, 10.0, 0.0)

        # Only the 3 kWh above the 20% floor may leave, at 0.9 efficiency.
        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(2.7)
        assert handle._charge_state == pytest.approx(2.0)
        assert handle._charge_percentage == 20

    def test_maximum_soc_limits_charge(self, make_handle):
        handle = make_handle()
        handle.set_slider_limit(80.0, "maximum_soc")
        update_after(handle, ONE_HOUR, 0.0, 10.0)

        assert handle._charge_state == pytest.approx(8.0)
        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(3.0 / 0.8)

    def test_minimum_soc_clamped_to_configured_floor(self, make_handle):
        handle = make_handle(
            base_config(**{CONF_MINIMUM_USER_SELECTABLE_SOC: 0.1})
        )
        assert handle._minimum_soc == 10.0

        handle.set_slider_limit(5.0, "minimum_soc")
        assert handle._minimum_soc == 10.0

        handle.set_slider_limit(25.0, "minimum_soc")
        assert handle._minimum_soc == 25.0

    def test_unknown_slider_key_logs_error(self, make_handle, caplog):
        handle = make_handle()
        handle.set_slider_limit(1.0, "bogus_key")
        assert "Unknown slider type" in caplog.text


class TestSolarLimits:
    """Solar production cap and inverter power sharing."""

    def test_solar_cap_limits_charging(self, make_handle):
        handle = make_handle(config_with_solar())
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 0.0, 5.0, solar=0.5)

        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(0.5)
        assert handle._sensors[SOLAR_POWER_CAP] == pytest.approx(0.5)
        assert handle._sensors[GRID_EXPORT_SIM] == pytest.approx(4.5)

    def test_inverter_power_shared_with_solar_limits_discharge(self, make_handle):
        handle = make_handle(config_with_solar(nominal_inverter_power=3.0))
        update_after(handle, ONE_HOUR, 5.0, 0.0, solar=0.5)

        # Inverter has 3.0 - 0.5 = 2.5 kW left for discharging.
        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(2.5)
        assert handle._sensors[DISCHARGING_RATE] == pytest.approx(2.5)

    def test_solar_amount_ignored_without_solar_sensor(self, make_handle):
        handle = make_handle()
        update_after(handle, ONE_HOUR, 0.0, 5.0, solar=0.1)

        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(4.0)
        assert handle._sensors[SOLAR_POWER_CAP] == 0.0


class TestTariffsAndSavings:
    """Money saved and tariff lookup behaviour."""

    def test_money_saved_on_import(self, make_handle):
        handle = make_handle(config_with_fixed_tariffs())
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 2.0, 0.0)

        assert handle._sensors[ATTR_MONEY_SAVED_IMPORT] == pytest.approx(
            2.0 * IMPORT_TARIFF
        )
        assert handle._sensors[ATTR_MONEY_SAVED_EXPORT] == pytest.approx(0.0)
        assert handle._sensors[ATTR_MONEY_SAVED] == pytest.approx(2.0 * IMPORT_TARIFF)

    def test_export_revenue_lost_while_charging(self, make_handle):
        handle = make_handle(config_with_fixed_tariffs())
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 0.0, 2.0)

        assert handle._sensors[ATTR_MONEY_SAVED_EXPORT] == pytest.approx(
            -2.0 * EXPORT_TARIFF
        )
        assert handle._sensors[ATTR_MONEY_SAVED] == pytest.approx(-2.0 * EXPORT_TARIFF)

    def test_no_money_tracked_without_tariffs(self, make_handle):
        handle = make_handle()
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 2.0, 0.0)

        assert handle._sensors[ATTR_MONEY_SAVED_IMPORT] == 0.0
        assert handle._sensors[ATTR_MONEY_SAVED_EXPORT] == 0.0
        assert handle._sensors[ATTR_MONEY_SAVED] == 0.0

    def test_get_tariff_information_fixed(self, make_handle):
        handle = make_handle(config_with_fixed_tariffs())
        assert handle.get_tariff_information(handle._inputs[0]) == IMPORT_TARIFF
        assert handle.get_tariff_information(handle._inputs[1]) == EXPORT_TARIFF

    def test_get_tariff_information_none_input(self, make_handle):
        handle = make_handle()
        assert handle.get_tariff_information(None) is None

    def test_get_tariff_information_no_tariff_type(self, make_handle):
        handle = make_handle()
        assert handle.get_tariff_information(handle._inputs[0]) is None

    def test_get_tariff_information_sensor(self, hass, make_handle):
        handle = make_handle(config_with_tariff_sensors())
        hass.states.async_set(IMPORT_TARIFF_SENSOR_ID, "0.25")
        hass.states.async_set(EXPORT_TARIFF_SENSOR_ID, "unavailable")

        assert handle.get_tariff_information(handle._inputs[0]) == pytest.approx(0.25)
        # Unavailable tariff sensors yield no tariff.
        assert handle.get_tariff_information(handle._inputs[1]) is None

    def test_get_tariff_information_missing_or_short_sensor(self, make_handle):
        handle = make_handle(config_with_tariff_sensors())
        # No state set at all.
        assert handle.get_tariff_information(handle._inputs[0]) is None

        handle._inputs[0][TARIFF_SENSOR] = "x.y"
        assert handle.get_tariff_information(handle._inputs[0]) is None

        handle._inputs[0][TARIFF_SENSOR] = None
        assert handle.get_tariff_information(handle._inputs[0]) is None


class TestStoredEnergyValue:
    """Monetary book value of the stored energy and its published average."""

    def test_charging_from_export_prices_energy_at_export_tariff(self, make_handle):
        handle = make_handle(config_with_fixed_tariffs())
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 0.0, 2.0)

        assert handle._stored_energy_value == pytest.approx(2.0 * EXPORT_TARIFF)
        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == pytest.approx(0.2 / 6.6)

    def test_forced_grid_charging_prices_energy_at_import_tariff(self, make_handle):
        handle = make_handle(config_with_fixed_tariffs())
        link_meter_readings(handle)
        handle._battery_mode = OVERRIDE_CHARGING
        update_after(handle, ONE_HOUR, 0.0, 0.0)

        assert handle._stored_energy_value == pytest.approx(4.0 * IMPORT_TARIFF)
        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == pytest.approx(1.2 / 8.2)

    def test_average_value_unchanged_by_discharge(self, make_handle):
        handle = make_handle(config_with_fixed_tariffs())
        link_meter_readings(handle)
        update_after(handle, ONE_HOUR, 0.0, 2.0)
        average_before = handle._sensors[ATTR_AVERAGE_ENERGY_VALUE]

        update_after(handle, ONE_HOUR, 1.0, 0.0)

        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == pytest.approx(
            average_before
        )
        assert handle._stored_energy_value == pytest.approx(
            0.2 * (1.0 - (1.0 / 0.9) / 6.6)
        )

    def test_average_value_excludes_reserved_floor_energy(self, make_handle):
        handle = make_handle(
            config_with_fixed_tariffs(**{CONF_MINIMUM_USER_SELECTABLE_SOC: 0.1})
        )
        link_meter_readings(handle)
        assert handle.non_dischargeable_capacity == pytest.approx(1.0)

        update_after(handle, ONE_HOUR, 0.0, 2.0)

        # The charged 0.2 cycles degrade capacity (and hence the floor) by a
        # few millionths of a kWh, so compare with an absolute tolerance.
        assert handle.dischargeable_stored_energy == pytest.approx(
            6.6 - 1.0, abs=1e-4
        )
        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == pytest.approx(
            0.2 / 5.6, abs=1e-5
        )


class TestDegradation:
    """Cycle counting and capacity degradation."""

    def test_degradation_factor_progression(self, make_handle):
        handle = make_handle()
        assert handle.degradation_factor == pytest.approx(1.0)
        assert handle.current_max_capacity == pytest.approx(10.0)

        handle._sensors[BATTERY_CYCLES] = 3000.0
        assert handle.degradation_factor == pytest.approx(0.9)
        assert handle.current_max_capacity == pytest.approx(9.0)

        handle._sensors[BATTERY_CYCLES] = 6000.0
        assert handle.degradation_factor == pytest.approx(0.8)

        # Degradation never drops below the configured end-of-life value.
        handle._sensors[BATTERY_CYCLES] = 9000.0
        assert handle.degradation_factor == pytest.approx(0.8)

    def test_custom_end_of_life_degradation(self, make_handle):
        handle = make_handle(base_config(**{CONF_END_OF_LIFE_DEGRADATION: 0.5}))
        handle._sensors[BATTERY_CYCLES] = 6000.0
        assert handle.degradation_factor == pytest.approx(0.5)

    def test_cycles_accumulate_from_charged_energy(self, make_handle):
        handle = make_handle()
        update_after(handle, ONE_HOUR, 0.0, 2.0)
        assert handle._sensors[BATTERY_CYCLES] == pytest.approx(0.2)

        update_after(handle, ONE_HOUR, 0.0, 2.0)
        assert handle._sensors[BATTERY_CYCLES] == pytest.approx(0.4)
        assert handle._sensors[BATTERY_DEGRADATION] == pytest.approx(
            1.0 - 0.2 * (0.4 / 6000.0)
        )


class TestDirectStateChanges:
    """Service-style direct changes of charge state, cycles and stored value."""

    def test_set_battery_charge_state(self, make_handle):
        handle = make_handle()
        handle.async_set_battery_charge_state(7.0)
        assert handle._charge_state == pytest.approx(7.0)

        handle.async_set_battery_charge_state(-3.0)
        assert handle._charge_state == 0.0

        handle.async_set_battery_charge_state(50.0)
        assert handle._charge_state == pytest.approx(10.0)

    def test_set_charge_state_preserves_average_value(self, make_handle):
        handle = make_handle()
        handle._stored_energy_value = 1.0
        handle._update_average_energy_value_sensor()
        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == pytest.approx(0.2)

        handle.async_set_battery_charge_state(2.5)
        assert handle._stored_energy_value == pytest.approx(0.5)
        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == pytest.approx(0.2)

        handle.async_set_battery_charge_state(0.0)
        assert handle._stored_energy_value == 0.0
        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == 0.0

    def test_raising_charge_from_zero_leaves_energy_unvalued(self, make_handle):
        handle = make_handle()
        handle.async_set_battery_charge_state(0.0)
        handle.async_set_battery_charge_state(5.0)

        assert handle._stored_energy_value == 0.0
        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == 0.0

    def test_set_battery_cycles_ages_battery(self, make_handle):
        handle = make_handle()
        handle.async_set_battery_cycles(3000.0)

        assert handle._sensors[BATTERY_CYCLES] == 3000.0
        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == pytest.approx(30000.0)
        assert handle._sensors[BATTERY_DEGRADATION] == pytest.approx(0.9)
        assert handle.current_max_capacity == pytest.approx(9.0)
        # Charge state below the new capacity stays put.
        assert handle._charge_state == pytest.approx(5.0)
        assert handle._charge_percentage == 56

    def test_set_battery_cycles_clips_charge_and_rescales_value(self, make_handle):
        handle = make_handle()
        handle._charge_state = 9.5
        handle._stored_energy_value = 0.95
        handle._update_average_energy_value_sensor()
        average_before = handle._sensors[ATTR_AVERAGE_ENERGY_VALUE]

        handle.async_set_battery_cycles(3000.0)

        assert handle._charge_state == pytest.approx(9.0)
        assert handle._stored_energy_value == pytest.approx(0.95 * 9.0 / 9.5)
        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == pytest.approx(
            average_before
        )

    def test_set_stored_energy_value(self, make_handle):
        handle = make_handle()
        handle.async_set_stored_energy_value(3.0)

        assert handle._stored_energy_value == 3.0
        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == pytest.approx(0.6)

    def test_get_efficiency(self, make_handle):
        handle = make_handle(
            base_config(**{CONF_BATTERY_CHARGE_EFFICIENCY: "0:0.8, 4:1.0"})
        )
        assert handle.get_efficiency("charge", 0.0) == pytest.approx(0.8)
        assert handle.get_efficiency("charge", 2.0) == pytest.approx(0.9)
        assert handle.get_efficiency("charge", 10.0) == pytest.approx(1.0)
        assert handle.get_efficiency("discharge", 3.0) == pytest.approx(0.9)

        with pytest.raises(ValueError):
            handle.get_efficiency("bogus", 1.0)


class TestEfficiencyCurves:
    """Power-dependent efficiency curves applied during updates."""

    def test_charge_uses_interpolated_efficiency(self, make_handle):
        handle = make_handle(
            base_config(**{CONF_BATTERY_CHARGE_EFFICIENCY: "0:0.8, 4:1.0"})
        )
        update_after(handle, ONE_HOUR, 0.0, 2.0)

        # 2 kW charging power interpolates to 0.9 efficiency.
        assert handle._sensors[ATTR_LAST_CHARGE_EFFICIENCY] == pytest.approx(0.9)
        assert handle._charge_state == pytest.approx(5.0 + 2.0 * 0.9)

    def test_discharge_uses_interpolated_efficiency(self, make_handle):
        handle = make_handle(
            base_config(**{CONF_BATTERY_DISCHARGE_EFFICIENCY: "0:1.0, 5:0.8"})
        )
        update_after(handle, ONE_HOUR, 2.0, 0.0)

        assert handle._sensors[ATTR_LAST_DISCHARGE_EFFICIENCY] == pytest.approx(0.92)
        assert handle._charge_state == pytest.approx(5.0 - 2.0 / 0.92)

    def test_legacy_single_efficiency_applies_to_both_directions(self, make_handle):
        config = base_config(**{CONF_BATTERY_EFFICIENCY: 0.85})
        del config[CONF_BATTERY_CHARGE_EFFICIENCY]
        del config[CONF_BATTERY_DISCHARGE_EFFICIENCY]
        handle = make_handle(config)

        assert handle._battery_charge_efficiency_curve == [(0.0, 0.85)]
        assert handle._battery_discharge_efficiency_curve == [(0.0, 0.85)]


class TestReset:
    """Resetting the battery to its initial state."""

    def test_reset_restores_initial_state(self, hass, make_handle):
        hass.states.async_set(IMPORT_SENSOR_ID, "123.4", KWH_ATTRIBUTES)
        hass.states.async_set(EXPORT_SENSOR_ID, "unavailable", KWH_ATTRIBUTES)

        handle = make_handle()
        handle._charge_state = 8.2
        handle._stored_energy_value = 2.0
        handle._sensors[ATTR_ENERGY_SAVED] = 7.0
        handle._sensors[ATTR_ENERGY_BATTERY_IN] = 9.0
        handle._sensors[ATTR_ENERGY_BATTERY_OUT] = 4.0
        handle._sensors[ATTR_MONEY_SAVED] = 3.0
        handle._sensors[BATTERY_MODE] = MODE_CHARGING

        handle.async_reset_battery()

        assert handle._charge_state == pytest.approx(5.0)
        assert handle._charge_percentage == 50
        assert handle._stored_energy_value == 0.0
        assert handle._sensors[ATTR_ENERGY_SAVED] == 0.0
        assert handle._sensors[ATTR_ENERGY_BATTERY_IN] == 0.0
        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == 0.0
        assert handle._sensors[ATTR_MONEY_SAVED] == 0.0
        assert handle._sensors[ATTR_AVERAGE_ENERGY_VALUE] == 0.0
        assert handle._sensors[BATTERY_MODE] == MODE_IDLE
        assert handle._sensors[ATTR_STATUS] == "Normal"
        assert handle._sensors[BATTERY_CYCLES] == 0.0
        assert handle._sensors[BATTERY_DEGRADATION] == 1.0
        # Simulated meters rebase onto the live readings where available.
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(123.4)
        assert handle._sensors[GRID_EXPORT_SIM] == 0.0


class TestMeterReadingHandlers:
    """State-change driven accumulation of import/export/solar readings."""

    async def test_import_readings_accumulate(self, hass, make_handle):
        handle = make_handle()
        hass.states.async_set(IMPORT_SENSOR_ID, "10.0", KWH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(IMPORT_SENSOR_ID, "12.5", KWH_ATTRIBUTES)
        await hass.async_block_till_done()

        assert handle._accumulated_import_reading == pytest.approx(2.5)
        assert handle._last_import_reading_sensor_data is handle._inputs[0]
        # Readings accumulate without updating the battery immediately.
        assert handle._charge_state == pytest.approx(5.0)

    async def test_watt_hour_readings_converted(self, hass, make_handle):
        handle = make_handle()
        hass.states.async_set(EXPORT_SENSOR_ID, "10000", WH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(EXPORT_SENSOR_ID, "12500", WH_ATTRIBUTES)
        await hass.async_block_till_done()

        assert handle._accumulated_export_reading == pytest.approx(2.5)

    async def test_unsupported_unit_ignored(self, hass, make_handle, caplog):
        handle = make_handle()
        attributes = dict(KWH_ATTRIBUTES, **{"unit_of_measurement": "MJ"})
        hass.states.async_set(IMPORT_SENSOR_ID, "5.0", attributes)
        await hass.async_block_till_done()
        hass.states.async_set(IMPORT_SENSOR_ID, "7.0", attributes)
        await hass.async_block_till_done()

        assert handle._accumulated_import_reading == 0.0
        assert "Unsupported energy unit" in caplog.text

    async def test_unavailable_transitions_ignored(self, hass, make_handle):
        handle = make_handle()
        hass.states.async_set(IMPORT_SENSOR_ID, "10.0", KWH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(IMPORT_SENSOR_ID, "unavailable", KWH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(IMPORT_SENSOR_ID, "12.0", KWH_ATTRIBUTES)
        await hass.async_block_till_done()

        assert handle._accumulated_import_reading == 0.0

    async def test_unchanged_reading_ignored(self, hass, make_handle):
        handle = make_handle()
        hass.states.async_set(IMPORT_SENSOR_ID, "10.0", KWH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(
            IMPORT_SENSOR_ID, "10.0", KWH_ATTRIBUTES, force_update=True
        )
        await hass.async_block_till_done()

        assert handle._accumulated_import_reading == 0.0

    async def test_decreasing_reading_rebases_simulated_sensor(
        self, hass, make_handle
    ):
        handle = make_handle()
        handle._sensors[GRID_IMPORT_SIM] = 9.0
        hass.states.async_set(IMPORT_SENSOR_ID, "10.0", KWH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(IMPORT_SENSOR_ID, "3.0", KWH_ATTRIBUTES)
        await hass.async_block_till_done()

        assert handle._accumulated_import_reading == 0.0
        assert handle._sensors[GRID_IMPORT_SIM] == pytest.approx(3.0)
        assert handle._sensors[DISCHARGING_RATE] == 0

    async def test_unknown_sensor_logs_warning(self, make_handle, caplog):
        handle = make_handle()
        event = Event("state_changed", {"entity_id": "sensor.not_tracked"})
        handle.async_reading_handler(event)

        assert "not found in input sensors" in caplog.text
        assert handle._accumulated_import_reading == 0.0

    async def test_solar_readings_accumulate(self, hass, make_handle):
        handle = make_handle(config_with_solar())
        hass.states.async_set(SOLAR_SENSOR_ID, "5.0", KWH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(SOLAR_SENSOR_ID, "5.4", KWH_ATTRIBUTES)
        await hass.async_block_till_done()

        assert handle._accumulated_solar_reading == pytest.approx(0.4)

    async def test_solar_meter_reset_clears_accumulation(self, hass, make_handle):
        handle = make_handle(config_with_solar())
        hass.states.async_set(SOLAR_SENSOR_ID, "5.0", KWH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(SOLAR_SENSOR_ID, "5.4", KWH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(SOLAR_SENSOR_ID, "0.1", KWH_ATTRIBUTES)
        await hass.async_block_till_done()

        assert handle._accumulated_solar_reading == 0.0


class TestUpdateScheduling:
    """Periodic updates and the minimum update interval."""

    async def test_periodic_update_applies_accumulated_readings(
        self, hass, make_handle, freezer
    ):
        handle = make_handle()
        hass.states.async_set(IMPORT_SENSOR_ID, "10.0", KWH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(IMPORT_SENSOR_ID, "12.5", KWH_ATTRIBUTES)
        await hass.async_block_till_done()

        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert handle._accumulated_import_reading == 0.0
        assert handle._charge_state == pytest.approx(5.0 - 2.5 / 0.9)
        assert handle._sensors[ATTR_ENERGY_BATTERY_OUT] == pytest.approx(2.5)

    async def test_trigger_update_within_minimum_interval_defers(
        self, hass, make_handle, freezer
    ):
        handle = make_handle()
        hass.states.async_set(IMPORT_SENSOR_ID, "10.0", KWH_ATTRIBUTES)
        await hass.async_block_till_done()
        hass.states.async_set(IMPORT_SENSOR_ID, "12.5", KWH_ATTRIBUTES)
        await hass.async_block_till_done()

        # No time has passed since the handle was created, so the update
        # must be deferred rather than applied.
        handle.async_trigger_update()
        assert handle._pending_update_cancel is not None
        assert handle._accumulated_import_reading == pytest.approx(2.5)
        assert handle._charge_state == pytest.approx(5.0)

        # A second trigger while one is pending must not schedule another.
        pending = handle._pending_update_cancel
        handle.async_trigger_update()
        assert handle._pending_update_cancel is pending

        freezer.tick(timedelta(seconds=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert handle._pending_update_cancel is None
        assert handle._accumulated_import_reading == 0.0
        assert handle._charge_state < 5.0

    async def test_trigger_update_after_minimum_interval_runs_immediately(
        self, make_handle
    ):
        handle = make_handle()
        handle._accumulated_import_reading = 1.0
        rewind_last_update(handle, ONE_HOUR)

        handle.async_trigger_update()

        assert handle._pending_update_cancel is None
        assert handle._accumulated_import_reading == 0.0
        assert handle._charge_state == pytest.approx(5.0 - 1.0 / 0.9)


class TestLegacyConfig:
    """Backwards compatibility with YAML-era configurations."""

    def test_inputs_generated_when_input_list_missing(self, make_handle):
        config = base_config()
        del config[CONF_INPUT_LIST]
        config[CONF_IMPORT_SENSOR] = IMPORT_SENSOR_ID
        config[CONF_EXPORT_SENSOR] = EXPORT_SENSOR_ID
        config[TARIFF_TYPE] = NO_TARIFF_INFO

        handle = make_handle(config)

        assert len(handle._inputs) == 2
        assert handle._inputs[0][TARIFF_TYPE] == NO_TARIFF_INFO
        assert GRID_IMPORT_SIM in handle._sensors
        assert GRID_EXPORT_SIM in handle._sensors

    def test_device_identifier_matching(self, hass, freezer):
        from custom_components.battery_sim import SimulatedBatteryHandle
        from custom_components.battery_sim.const import DOMAIN

        handle = SimulatedBatteryHandle(base_config(), hass, entry_id="entry-id-1")
        try:
            assert handle.device_identifier == (DOMAIN, "entry-id-1")
            assert handle.matches_device_identifiers({(DOMAIN, "entry-id-1")})
            # Devices created before entry ids were used match on the name.
            assert handle.matches_device_identifiers({(DOMAIN, "test_battery")})
            assert not handle.matches_device_identifiers({(DOMAIN, "other")})
            assert not handle.matches_device_identifiers({("other", "entry-id-1")})
        finally:
            for unsub in handle._listeners:
                unsub()
            handle._listeners.clear()
