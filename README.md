# Battery Simulator integration/custom component for home assistant

[![downloads](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.battery_sim.versions[%271.0%27])](https://github.com/hif2k1/battery_sim/)

Allows you to model how much energy you would save with a home battery if you currently export energy to the grid e.g. from solar panels. Requires an energy monitor that can measure import and export energy. Whenever you are exporting energy your simulated battery will charge up and whenevery you are importing it will discharge. Battery charge percentage and total energy saved are in the attributes. 

Please note this is a simulation and a real battery may behave differently and not all batteries will support all the features available in this simulation. In particular battery_sim allows you to simulate batteries that charge and discharge across multiple phases and various modes including charge_only, discharge_only etc that may not be available in all real world batteries. 

## Setup

The easiest way to get battery_sim is to use HACS to add it as an integration. If you don't want to use HACS you can just copy the code into the custom_components folder in your home assistant config folder. 

Once you have done this you need to create your batteries. You can create any custom battery you want or use batteries with parameters the same as some common available models. The recommended way to do this is by going to **Settings > Devices and Services** and then clicking **Add Integration** and search for **Battery Simulation** and then work through the dialogue to create your battery. Repeat this process for each battery you want to add. 

Alternatively you can add your battery to the home assistant configuration file.

The relevant parameters are:
- import_sensor: the sensor that measures the energy in kwh imported (coming into) your house cummlatively (e.g. output of a utility_meter component)
- export_sensor: the sensor that measures the energy in kwh exported (leaving - sometimes called injection) your house cummlatively (e.g. output of a utility_meter component)
- size_kwh: the maximum usable capacity of the battery in kwh - must be floating point number (with a decimal point e.g. 5.0)
- max_discharge_rate_kw: how fast the battery can discharge in kw - must be floating point number (with a decimal point e.g. 5.0)
- max_charge_rate_kw: how fast the battery can charge in kw - must be floating point number (with a decimal point e.g. 5.0)
- efficiency - the round trip efficiency of the battery (0-1). This factor is applied on discharging the battery.
- energy_tariff - (optional) the sensor that tracks the energy tarriff - units not supported at present.

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
    energy_tariff: 0.184
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

## Energy Dashboard

You can configure battery_sim to display your simulated battery on your Energy Dashboard:

![Screenshot 2022-03-15 19 36 47](https://user-images.githubusercontent.com/79175134/158349586-cfc64761-0614-4067-a18a-5603d2288d7c.png)


![image](https://user-images.githubusercontent.com/79175134/157999078-0174ab36-9f71-47c8-8585-73d6eb3acec8.png)

## Debug

If you are having problems it is helpful to get the debug log for the battery by adding:

```
logger:
  default: critical
  logs:
    custom_components.battery_sim: debug
```

to your configuration.yaml and then restarting. If you leave it to run for a few minutes go to logs then and click "load full log" you should see entries from the battery saying it's been set up and then each time it receives an update. If you need to raise an issue then including this code is helpful.
