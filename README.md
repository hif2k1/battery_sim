# Battery Simulator integration/custom component for home assistant

Allows you to model how much energy you would save with a home battery if you currently export energy to the grid e.g. from solar panels. Requires an energy monitor that can measure import and export energy. Whenever you are exporting energy your simulated battery will charge up and whenevery you are importing it will discharge. Battery charge percentage and total energy saved are in the attributes. 

# Example configuration

You can create any custom battery you want, but below is the config for some common batteries.
import_sensor - the sensor that measures the energy in kwh imported to your house cummlatively (e.g. output of a utility_meter component)
export_sensor - the sensor that measures the energy in kwh exported to your house cummlatively (e.g. output of a utility_meter component)
size_kwh - the maximum usable capacity of the battery in kwh - must be floating point number (with a decimal point e.g. 5.0)
max_discharge_rate_kw/max_charge_rate_kw - how fast the battery can discharge/charge in kw - must be floating point number (with a decimal point e.g. 5.0)
efficiency - the round trip efficiency of the battery (0-1)

```yaml
battery_sim:
  tesla_powerwall:
    name: Tesla Powerwall
    import_sensor: sensor.circuitsetup_cumulative_import_energy_kwh
    export_sensor: sensor.circuitsetup_cumulative_export_energy_kwh
    size_kwh: 13.5
    max_discharge_rate_kw: 5.0
    max_charge_rate_kw: 3.68
    efficiency: 0.9
  lg_chem_resu10h:
    name: LG Chem
    import_sensor: sensor.circuitsetup_cumulative_import_energy_kwh
    export_sensor: sensor.circuitsetup_cumulative_export_energy_kwh
    size_kwh: 9.3
    max_discharge_rate_kw: 5.0
    max_charge_rate_kw: 3.3
    efficiency: 0.95
  sonnen_eco:
    name: Sonnen Eco
    import_sensor: sensor.circuitsetup_cumulative_import_energy_kwh
    export_sensor: sensor.circuitsetup_cumulative_export_energy_kwh
    size_kwh: 5.0
    max_discharge_rate_kw: 2.5
    max_charge_rate_kw: 2.5
    efficiency: 0.9
  pika_harbour:
    name: Pika Harbour
    import_sensor: sensor.circuitsetup_cumulative_import_energy_kwh
    export_sensor: sensor.circuitsetup_cumulative_export_energy_kwh
    size_kwh: 8.6
    max_discharge_rate_kw: 4.2
    max_charge_rate_kw: 4.2
    efficiency: 0.965
   ```
