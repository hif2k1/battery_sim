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
    SIMULATED_SENSOR
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
            TARIFF_TYPE: tariff_type
        },
        {
            SENSOR_ID: config[CONF_EXPORT_SENSOR],
            SENSOR_TYPE: EXPORT,
            SIMULATED_SENSOR: GRID_EXPORT_SIM,
            TARIFF_TYPE: tariff_type
        },
    ]
    if len(config.get(CONF_SECOND_IMPORT_SENSOR, "")) > 6:
        inputs.append({
            SENSOR_ID: config[CONF_SECOND_IMPORT_SENSOR],
            SENSOR_TYPE: IMPORT,
            SIMULATED_SENSOR: GRID_SECOND_IMPORT_SIM,
            TARIFF_TYPE: tariff_type
        })
    if len(config.get(CONF_SECOND_EXPORT_SENSOR, "")) > 6:
        inputs.append({
            SENSOR_ID: config[CONF_SECOND_EXPORT_SENSOR],
            SENSOR_TYPE: EXPORT,
            SIMULATED_SENSOR: GRID_SECOND_EXPORT_SIM,
            TARIFF_TYPE: tariff_type
        })

    """Default sensor entities for backwards compatibility"""
    if CONF_ENERGY_IMPORT_TARIFF in config:
        inputs[0][tariff_type] = config[CONF_ENERGY_IMPORT_TARIFF]
    elif CONF_ENERGY_TARIFF in config:
        """For backwards compatibility"""
        inputs[0][tariff_type] = config[CONF_ENERGY_TARIFF]

    if CONF_ENERGY_EXPORT_TARIFF in config:
        inputs[1][tariff_type] = config[CONF_ENERGY_EXPORT_TARIFF]
    if CONF_SECOND_ENERGY_IMPORT_TARIFF in config:
        inputs[2][tariff_type] = config[CONF_SECOND_ENERGY_IMPORT_TARIFF]
    if CONF_SECOND_ENERGY_EXPORT_TARIFF in config:
        inputs[3][tariff_type] = config[CONF_SECOND_ENERGY_EXPORT_TARIFF]
    return inputs