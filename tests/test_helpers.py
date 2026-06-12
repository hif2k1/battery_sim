"""Tests for battery_sim helper functions."""
from types import SimpleNamespace

import pytest

from homeassistant.const import CONF_NAME
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.battery_sim.const import (
    CONF_ENERGY_EXPORT_TARIFF,
    CONF_ENERGY_IMPORT_TARIFF,
    CONF_ENERGY_TARIFF,
    CONF_EXPORT_SENSOR,
    CONF_IMPORT_SENSOR,
    CONF_SECOND_ENERGY_EXPORT_TARIFF,
    CONF_SECOND_ENERGY_IMPORT_TARIFF,
    CONF_SECOND_EXPORT_SENSOR,
    CONF_SECOND_IMPORT_SENSOR,
    CONF_SOLAR_ENERGY_SENSOR,
    DOMAIN,
    EXPORT,
    FIXED_NUMERICAL_TARIFFS,
    FIXED_TARIFF,
    GRID_EXPORT_SIM,
    GRID_IMPORT_SIM,
    GRID_SECOND_EXPORT_SIM,
    GRID_SECOND_IMPORT_SIM,
    IMPORT,
    NO_TARIFF_INFO,
    SENSOR_ID,
    SENSOR_TYPE,
    SIMULATED_SENSOR,
    SOLAR_POWER_CAP,
    TARIFF_SENSOR,
    TARIFF_TYPE,
)
from custom_components.battery_sim.helpers import (
    battery_device_identifiers,
    device_display_name,
    expected_entity_unique_ids,
    find_empty_battery_devices,
    find_leftover_entity_registry_entries,
    generate_input_list,
    interpolate_efficiency,
    parse_efficiency_curve,
    purge_leftover_battery_registry_entries,
    validate_efficiency_config,
)

from .common import BATTERY_NAME, base_config


class TestParseEfficiencyCurve:
    """Tests for parse_efficiency_curve."""

    def test_float_value(self):
        assert parse_efficiency_curve(0.95) == [(0.0, 0.95)]

    def test_int_value(self):
        assert parse_efficiency_curve(1) == [(0.0, 1.0)]

    def test_numeric_string(self):
        assert parse_efficiency_curve("0.85") == [(0.0, 0.85)]

    def test_numeric_string_with_whitespace(self):
        assert parse_efficiency_curve("  0.85  ") == [(0.0, 0.85)]

    def test_none_raises(self):
        with pytest.raises(ValueError):
            parse_efficiency_curve(None)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_efficiency_curve("   ")

    def test_unparseable_text_raises(self):
        with pytest.raises(ValueError):
            parse_efficiency_curve("not an efficiency")

    @pytest.mark.parametrize("value", [1.5, -0.1, "1.2"])
    def test_out_of_range_value_raises(self, value):
        with pytest.raises(ValueError):
            parse_efficiency_curve(value)

    def test_colon_separated_pairs(self):
        assert parse_efficiency_curve("0:0.9, 5:0.95") == [(0.0, 0.9), (5.0, 0.95)]

    def test_parenthesised_pairs(self):
        assert parse_efficiency_curve("(0, 0.9), (5, 0.95)") == [
            (0.0, 0.9),
            (5.0, 0.95),
        ]

    def test_semicolon_separated_pairs(self):
        assert parse_efficiency_curve("0:0.9; 5:0.95") == [(0.0, 0.9), (5.0, 0.95)]

    def test_pairs_sorted_by_power(self):
        assert parse_efficiency_curve("5:0.95, 0:0.9, 2:0.92") == [
            (0.0, 0.9),
            (2.0, 0.92),
            (5.0, 0.95),
        ]

    def test_duplicate_power_last_value_wins(self):
        assert parse_efficiency_curve("0:0.9, 0:0.8") == [(0.0, 0.8)]

    def test_negative_power_raises(self):
        with pytest.raises(ValueError):
            parse_efficiency_curve("-1:0.9, 5:0.95")

    def test_curve_efficiency_out_of_range_raises(self):
        with pytest.raises(ValueError):
            parse_efficiency_curve("0:0.9, 5:1.5")


class TestValidateEfficiencyConfig:
    """Tests for validate_efficiency_config."""

    @pytest.mark.parametrize("value", [0.9, "0.9", "0:0.8, 5:0.95"])
    def test_valid_value_returned_unchanged(self, value):
        assert validate_efficiency_config(value) == value

    @pytest.mark.parametrize("value", [None, "", "bogus", 1.7])
    def test_invalid_value_raises(self, value):
        with pytest.raises(ValueError):
            validate_efficiency_config(value)


class TestInterpolateEfficiency:
    """Tests for interpolate_efficiency."""

    def test_single_point_is_constant(self):
        curve = [(0.0, 0.9)]
        assert interpolate_efficiency(curve, 0.0) == 0.9
        assert interpolate_efficiency(curve, 100.0) == 0.9

    def test_below_first_point_returns_first(self):
        curve = [(2.0, 0.8), (5.0, 0.9)]
        assert interpolate_efficiency(curve, 1.0) == 0.8

    def test_above_last_point_returns_last(self):
        curve = [(0.0, 0.8), (5.0, 0.9)]
        assert interpolate_efficiency(curve, 50.0) == 0.9

    def test_linear_interpolation_midpoint(self):
        curve = [(0.0, 0.8), (10.0, 1.0)]
        assert interpolate_efficiency(curve, 5.0) == pytest.approx(0.9)

    def test_exact_curve_points(self):
        curve = [(0.0, 0.8), (4.0, 0.9), (8.0, 0.7)]
        assert interpolate_efficiency(curve, 0.0) == 0.8
        assert interpolate_efficiency(curve, 4.0) == pytest.approx(0.9)
        assert interpolate_efficiency(curve, 8.0) == pytest.approx(0.7)

    def test_interpolation_across_segments(self):
        curve = [(0.0, 0.8), (4.0, 0.9), (8.0, 0.7)]
        assert interpolate_efficiency(curve, 2.0) == pytest.approx(0.85)
        assert interpolate_efficiency(curve, 6.0) == pytest.approx(0.8)

    def test_empty_curve_raises(self):
        with pytest.raises(ValueError):
            interpolate_efficiency([], 1.0)


class TestGenerateInputList:
    """Tests for the legacy-config input list generation."""

    BASE = {
        CONF_IMPORT_SENSOR: "sensor.import_energy",
        CONF_EXPORT_SENSOR: "sensor.export_energy",
    }

    def test_basic_import_and_export(self):
        inputs = generate_input_list(dict(self.BASE))
        assert len(inputs) == 2
        assert inputs[0] == {
            SENSOR_ID: "sensor.import_energy",
            SENSOR_TYPE: IMPORT,
            SIMULATED_SENSOR: GRID_IMPORT_SIM,
            TARIFF_TYPE: TARIFF_SENSOR,
        }
        assert inputs[1] == {
            SENSOR_ID: "sensor.export_energy",
            SENSOR_TYPE: EXPORT,
            SIMULATED_SENSOR: GRID_EXPORT_SIM,
            TARIFF_TYPE: TARIFF_SENSOR,
        }

    def test_no_tariff_info_type(self):
        config = dict(self.BASE)
        config[TARIFF_TYPE] = NO_TARIFF_INFO
        inputs = generate_input_list(config)
        assert all(entry[TARIFF_TYPE] == NO_TARIFF_INFO for entry in inputs)

    def test_fixed_tariffs(self):
        config = dict(self.BASE)
        config[TARIFF_TYPE] = FIXED_NUMERICAL_TARIFFS
        config[CONF_ENERGY_IMPORT_TARIFF] = 0.3
        config[CONF_ENERGY_EXPORT_TARIFF] = 0.1
        inputs = generate_input_list(config)
        assert inputs[0][TARIFF_TYPE] == FIXED_TARIFF
        assert inputs[0][FIXED_TARIFF] == 0.3
        assert inputs[1][FIXED_TARIFF] == 0.1

    def test_tariff_sensors(self):
        config = dict(self.BASE)
        config[CONF_ENERGY_IMPORT_TARIFF] = "sensor.import_price"
        config[CONF_ENERGY_EXPORT_TARIFF] = "sensor.export_price"
        inputs = generate_input_list(config)
        assert inputs[0][TARIFF_SENSOR] == "sensor.import_price"
        assert inputs[1][TARIFF_SENSOR] == "sensor.export_price"

    def test_legacy_energy_tariff_used_for_import(self):
        config = dict(self.BASE)
        config[CONF_ENERGY_TARIFF] = "sensor.legacy_price"
        inputs = generate_input_list(config)
        assert inputs[0][TARIFF_SENSOR] == "sensor.legacy_price"
        assert TARIFF_SENSOR not in inputs[1]

    def test_second_import_and_export_sensors(self):
        config = dict(self.BASE)
        config[CONF_SECOND_IMPORT_SENSOR] = "sensor.import_energy_2"
        config[CONF_SECOND_EXPORT_SENSOR] = "sensor.export_energy_2"
        config[CONF_SECOND_ENERGY_IMPORT_TARIFF] = "sensor.import_price_2"
        config[CONF_SECOND_ENERGY_EXPORT_TARIFF] = "sensor.export_price_2"
        inputs = generate_input_list(config)
        assert len(inputs) == 4
        assert inputs[2][SIMULATED_SENSOR] == GRID_SECOND_IMPORT_SIM
        assert inputs[2][SENSOR_TYPE] == IMPORT
        assert inputs[2][TARIFF_SENSOR] == "sensor.import_price_2"
        assert inputs[3][SIMULATED_SENSOR] == GRID_SECOND_EXPORT_SIM
        assert inputs[3][SENSOR_TYPE] == EXPORT
        assert inputs[3][TARIFF_SENSOR] == "sensor.export_price_2"

    def test_short_second_sensor_values_ignored(self):
        config = dict(self.BASE)
        config[CONF_SECOND_IMPORT_SENSOR] = ""
        config[CONF_SECOND_EXPORT_SENSOR] = "x.y"
        inputs = generate_input_list(config)
        assert len(inputs) == 2


class TestExpectedEntityUniqueIds:
    """Tests for expected_entity_unique_ids."""

    def test_contains_battery_and_all_per_input_sensors(self):
        unique_ids = expected_entity_unique_ids(base_config())
        assert BATTERY_NAME in unique_ids
        assert f"{BATTERY_NAME} - total energy saved" in unique_ids
        assert f"{BATTERY_NAME} - {GRID_IMPORT_SIM}" in unique_ids
        assert f"{BATTERY_NAME} - {GRID_EXPORT_SIM}" in unique_ids
        assert f"{BATTERY_NAME} - Battery Mode" in unique_ids
        assert f"{BATTERY_NAME} - charge_limit" in unique_ids
        # battery + 14 base sensors + 2 inputs + 7 control entities
        assert len(unique_ids) == 24

    def test_solar_config_adds_solar_power_cap(self):
        config = base_config()
        config[CONF_SOLAR_ENERGY_SENSOR] = "sensor.solar"
        unique_ids = expected_entity_unique_ids(config)
        assert f"{BATTERY_NAME} - {SOLAR_POWER_CAP}" in unique_ids
        assert len(unique_ids) == 25

    def test_no_solar_excludes_solar_power_cap(self):
        unique_ids = expected_entity_unique_ids(base_config())
        assert f"{BATTERY_NAME} - {SOLAR_POWER_CAP}" not in unique_ids

    def test_legacy_config_without_input_list(self):
        config = {
            CONF_NAME: "legacy",
            CONF_IMPORT_SENSOR: "sensor.import_energy",
            CONF_EXPORT_SENSOR: "sensor.export_energy",
        }
        unique_ids = expected_entity_unique_ids(config)
        assert f"legacy - {GRID_IMPORT_SIM}" in unique_ids
        assert f"legacy - {GRID_EXPORT_SIM}" in unique_ids


def test_battery_device_identifiers_without_entry_id():
    assert battery_device_identifiers(base_config()) == [(DOMAIN, BATTERY_NAME)]


def test_battery_device_identifiers_with_entry_id():
    assert battery_device_identifiers(base_config(), "entry123") == [
        (DOMAIN, "entry123"),
        (DOMAIN, BATTERY_NAME),
    ]


@pytest.mark.parametrize(
    ("name_by_user", "name", "expected"),
    [
        ("Renamed", "Original", "Renamed"),
        (None, "Original", "Original"),
        (None, None, "device-id"),
    ],
)
def test_device_display_name(name_by_user, name, expected):
    device = SimpleNamespace(name_by_user=name_by_user, name=name, id="device-id")
    assert device_display_name(device) == expected


class TestRegistryCleanupHelpers:
    """Tests for leftover entity and empty device detection/purging."""

    async def _setup_with_leftovers(self, hass, setup_battery):
        """Set up a battery and add a stale entity plus an empty legacy device."""
        entry, _handle = await setup_battery()
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, entry.entry_id)}
        )
        assert device is not None

        stale = entity_registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{BATTERY_NAME} - obsolete sensor",
            config_entry=entry,
            device_id=device.id,
        )
        # An entity from another integration must never be touched.
        foreign = entity_registry.async_get_or_create(
            "sensor",
            "template",
            "unrelated unique id",
            device_id=device.id,
        )
        legacy_device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, BATTERY_NAME)},
            name="legacy device",
        )
        return entry, entity_registry, device_registry, stale, foreign, legacy_device

    async def test_no_leftovers_for_clean_setup(self, hass, setup_battery):
        entry, _handle = await setup_battery()
        entity_registry = er.async_get(hass)
        device_registry = dr.async_get(hass)
        assert (
            find_leftover_entity_registry_entries(
                entity_registry, device_registry, entry.data, entry.entry_id
            )
            == []
        )
        assert (
            find_empty_battery_devices(
                entity_registry, device_registry, entry.data, entry.entry_id
            )
            == []
        )

    async def test_find_leftover_entities(self, hass, setup_battery):
        (
            entry,
            entity_registry,
            device_registry,
            stale,
            _foreign,
            _legacy_device,
        ) = await self._setup_with_leftovers(hass, setup_battery)

        leftovers = find_leftover_entity_registry_entries(
            entity_registry, device_registry, entry.data, entry.entry_id
        )
        assert [entry_.entity_id for entry_ in leftovers] == [stale.entity_id]

    async def test_find_empty_devices(self, hass, setup_battery):
        (
            entry,
            entity_registry,
            device_registry,
            _stale,
            _foreign,
            legacy_device,
        ) = await self._setup_with_leftovers(hass, setup_battery)

        empty = find_empty_battery_devices(
            entity_registry, device_registry, entry.data, entry.entry_id
        )
        assert [device.id for device in empty] == [legacy_device.id]

    async def test_purge_removes_stale_entity_and_empty_device(
        self, hass, setup_battery
    ):
        (
            entry,
            entity_registry,
            device_registry,
            stale,
            foreign,
            legacy_device,
        ) = await self._setup_with_leftovers(hass, setup_battery)

        removed_entities, removed_devices = purge_leftover_battery_registry_entries(
            entity_registry, device_registry, entry.data, entry.entry_id
        )

        assert removed_entities == [stale.entity_id]
        assert removed_devices == ["legacy device"]
        assert entity_registry.async_get(stale.entity_id) is None
        assert entity_registry.async_get(foreign.entity_id) is not None
        assert device_registry.async_get(legacy_device.id) is None
        # The active battery device and its entities stay untouched.
        assert (
            device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
            is not None
        )
        assert entity_registry.async_get("sensor.test_battery") is not None

    async def test_purge_with_nothing_to_remove(self, hass, setup_battery):
        entry, _handle = await setup_battery()
        removed_entities, removed_devices = purge_leftover_battery_registry_entries(
            er.async_get(hass), dr.async_get(hass), entry.data, entry.entry_id
        )
        assert removed_entities == []
        assert removed_devices == []
