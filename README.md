# Battery Simulator integration/custom component for home assistant

Allows you to model how much energy you would save with a home battery if you currently export energy to the grid. Requires an energy monitor that can measure import and export energy.

# Example configuration

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
