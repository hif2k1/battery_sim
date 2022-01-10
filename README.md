# Battery Simulator integration/custom component for home assistant

Allows you to model how much energy you would save with a home battery if you currently export energy to the grid e.g. from solar panels. Requires an energy monitor that can measure import and export energy. Whenever you are exporting energy your simulated battery will charge up and whenevery you are importing it will discharge. Battery charge percentage and total energy saved are in the attributes. 

# Setup

The easiest way to get battery_sim is to use HACS to add it as an integration. Once you have done this you need to add an entry in your home assistant config file to specify the batteries you want to simulate. If you don't want to use HACS you can just copy the code into the custom integrations folder in your home assistant config folder. 

# Example configuration

You can create any custom battery you want, but below is the config for some common batteries.
- import_sensor: the sensor that measures the energy in kwh imported (coming into) your house cummlatively (e.g. output of a utility_meter component)
- export_sensor: the sensor that measures the energy in kwh exported (leaving - sometimes called injection) your house cummlatively (e.g. output of a utility_meter component)
- size_kwh: the maximum usable capacity of the battery in kwh - must be floating point number (with a decimal point e.g. 5.0)
- max_discharge_rate_kw: how fast the battery can discharge in kw - must be floating point number (with a decimal point e.g. 5.0)
- max_charge_rate_kw: how fast the battery can charge in kw - must be floating point number (with a decimal point e.g. 5.0)
- efficiency - the round trip efficiency of the battery (0-1). This factor is applied on discharging the battery.
- energy_tariff - (optional) for use with variable energy tarrifs. If provided will count money saved by multiplying discharge from the battery by current tarrif. Currently no support for currency symbols so only enter number value.

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
    energy_tarriff: 0.184
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
