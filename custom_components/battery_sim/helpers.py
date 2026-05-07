import re

from .const import (
    CONF_ENERGY_EXPORT_TARIFF,
    CONF_ENERGY_IMPORT_TARIFF,
    CONF_ENERGY_TARIFF,
    CONF_EXPORT_SENSOR,
    CONF_IMPORT_SENSOR,
    CONF_SECOND_EXPORT_SENSOR,
    CONF_SECOND_IMPORT_SENSOR,
    FIXED_NUMERICAL_TARIFFS,
    GRID_EXPORT_SIM,
    GRID_IMPORT_SIM,
    GRID_SECOND_EXPORT_SIM,
    GRID_SECOND_IMPORT_SIM,
    NO_TARIFF_INFO,
    FIXED_TARIFF,
    TARIFF_TYPE,
    SENSOR_ID,
    SENSOR_TYPE,
    TARIFF_SENSOR,
    CONF_SECOND_ENERGY_IMPORT_TARIFF,
    CONF_SECOND_ENERGY_EXPORT_TARIFF,
    IMPORT,
    EXPORT,
    SIMULATED_SENSOR,
)

"""For backwards compatability with old configs"""


def generate_input_list(config):
    tariff_type: str = TARIFF_SENSOR
    if TARIFF_TYPE in config:
        if config[TARIFF_TYPE] == NO_TARIFF_INFO:
            tariff_type = NO_TARIFF_INFO
        elif config[TARIFF_TYPE] == FIXED_NUMERICAL_TARIFFS:
            tariff_type = FIXED_TARIFF

    inputs = [
        {
            SENSOR_ID: config[CONF_IMPORT_SENSOR],
            SENSOR_TYPE: IMPORT,
            SIMULATED_SENSOR: GRID_IMPORT_SIM,
            TARIFF_TYPE: tariff_type,
        },
        {
            SENSOR_ID: config[CONF_EXPORT_SENSOR],
            SENSOR_TYPE: EXPORT,
            SIMULATED_SENSOR: GRID_EXPORT_SIM,
            TARIFF_TYPE: tariff_type,
        },
    ]
    if len(config.get(CONF_SECOND_IMPORT_SENSOR, "")) > 6:
        inputs.append(
            {
                SENSOR_ID: config[CONF_SECOND_IMPORT_SENSOR],
                SENSOR_TYPE: IMPORT,
                SIMULATED_SENSOR: GRID_SECOND_IMPORT_SIM,
                TARIFF_TYPE: tariff_type,
            }
        )
    if len(config.get(CONF_SECOND_EXPORT_SENSOR, "")) > 6:
        inputs.append(
            {
                SENSOR_ID: config[CONF_SECOND_EXPORT_SENSOR],
                SENSOR_TYPE: EXPORT,
                SIMULATED_SENSOR: GRID_SECOND_EXPORT_SIM,
                TARIFF_TYPE: tariff_type,
            }
        )

    """Default sensor entities for backwards compatibility"""
    if CONF_ENERGY_IMPORT_TARIFF in config:
        inputs[0][tariff_type] = config[CONF_ENERGY_IMPORT_TARIFF]
    elif CONF_ENERGY_TARIFF in config:
        """For backwards compatibility"""
        inputs[0][tariff_type] = config[CONF_ENERGY_TARIFF]

    if CONF_ENERGY_EXPORT_TARIFF in config:
        inputs[1][tariff_type] = config[CONF_ENERGY_EXPORT_TARIFF]

    def _set_tariff_for_sensor(simulated_sensor, tariff_config_key):
        if tariff_config_key not in config:
            return
        matching_input = next(
            (
                input_entry
                for input_entry in inputs
                if input_entry[SIMULATED_SENSOR] == simulated_sensor
            ),
            None,
        )
        if matching_input is not None:
            matching_input[tariff_type] = config[tariff_config_key]

    _set_tariff_for_sensor(
        GRID_SECOND_IMPORT_SIM,
        CONF_SECOND_ENERGY_IMPORT_TARIFF,
    )
    _set_tariff_for_sensor(
        GRID_SECOND_EXPORT_SIM,
        CONF_SECOND_ENERGY_EXPORT_TARIFF,
    )
    return inputs


def parse_efficiency_curve(raw_value):
    """Parse an efficiency config value into sorted (power_kw, efficiency) points."""
    if isinstance(raw_value, (int, float)):
        value = float(raw_value)
        _validate_efficiency(value)
        return [(0.0, value)]

    if raw_value is None:
        raise ValueError("Efficiency value is required")

    text = str(raw_value).strip()
    if not text:
        raise ValueError("Efficiency value is required")

    try:
        value = float(text)
    except ValueError:
        value = None

    if value is not None:
        _validate_efficiency(value)
        return [(0.0, value)]

    normalized = text.replace(";", ",")
    pair_matches = re.findall(
        r"\(?\s*(-?\d+(?:\.\d+)?)\s*[,:\s]\s*(-?\d+(?:\.\d+)?)\s*\)?",
        normalized,
    )
    if not pair_matches:
        raise ValueError(
            "Use a number like 0.95 or power/efficiency pairs like 0:0.9, 5:0.95"
        )

    points = []
    for power_text, efficiency_text in pair_matches:
        power = float(power_text)
        efficiency = float(efficiency_text)
        if power < 0:
            raise ValueError("Efficiency curve power values must be >= 0")
        _validate_efficiency(efficiency)
        points.append((power, efficiency))

    points.sort(key=lambda item: item[0])
    deduplicated_points = []
    for power, efficiency in points:
        if deduplicated_points and power == deduplicated_points[-1][0]:
            deduplicated_points[-1] = (power, efficiency)
        else:
            deduplicated_points.append((power, efficiency))
    return deduplicated_points


def validate_efficiency_config(raw_value):
    """Validate the configured efficiency value or curve and return the raw value."""
    parse_efficiency_curve(raw_value)
    return raw_value


def interpolate_efficiency(curve_points, power_kw):
    """Return the efficiency for the requested power using linear interpolation."""
    if not curve_points:
        raise ValueError("Efficiency curve must contain at least one point")

    if len(curve_points) == 1 or power_kw <= curve_points[0][0]:
        return curve_points[0][1]

    for (start_power, start_efficiency), (end_power, end_efficiency) in zip(
        curve_points, curve_points[1:]
    ):
        if power_kw <= end_power:
            if end_power == start_power:
                return end_efficiency
            ratio = (power_kw - start_power) / (end_power - start_power)
            return start_efficiency + ratio * (end_efficiency - start_efficiency)

    return curve_points[-1][1]


def _validate_efficiency(value):
    if not 0 <= value <= 1:
        raise ValueError("Efficiency values must be between 0 and 1")
