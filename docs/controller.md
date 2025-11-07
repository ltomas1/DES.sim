# controller.py — Module documentation

## Overview

`controller.py` implements a simulation controller for a heating/cooling system. The main responsibilities are:

- Matching heating demands (space heating and domestic hot water) with supply from tanks and backup heaters.
- Controlling generators behavior using configurable control strategies.
- Computing tank flows, temperatures, and the output heat delivered to consumers.

The module contains these main classes:

- `Controller` — primary model tying together sensors, tanks, and generators.
- `TCValve` — simplified temperature-controlled 3-way mixing valve model.
- `idealHeatRod` — idealized electric heating rod helper used to identify component undersizing.
- `IncompleteConfigError` — small exception used by `idealHeatRod`.

## Controller

Purpose
: Simulation model of a controller which implements Boolean/threshold logic to operate generators, heating rods and mixing valves.

Instantiation
: `ctrl = Controller(params)`

Key init parameters (passed in the `params` dict)

- `control_strategy` — str, default `'1'`: picks the generator/HP control logic to use.
- `Ideal_hr_mode` — str, default `'off'`: enables the ideal heating rod behaviour when `'on'`.
- `supply_config` — str: selects tank topology/branching for supply calculations (2/3/4-runner).
- `sh_out` — str: tank connection used to supply the space heating demand.
- `sh_out2` — str|None: optional secondary (hot) source used to supply space heating demand.
- `dhw_out` — str: tank connection port used to supply drinking hot water demand.
- `return_tank` — str: target port for aggregated return flows (required for `2-`and `3-runner` setups).
- `sh_ret` — str|None: dedicated space-heating return port (4-runner only).
- `dhw_ret` — str|None: dedicated DHW return port (4-runner only).
- `dhw_Tdelta` — numeric, default `15`: temperature difference between DHW supply and return.
- `T_dhw_sp` — numeric|None: DHW supply temperature setpoint used by ideal heater logic.
- `heat_dT` — numeric: temperature difference used for 2-runner heat calculation (defaults to `dhw_Tdelta`).

- `step_size` — numeric: simulation step size in seconds (attribute stored as `self.stepsize`).
- `tank` — dict: nested tank configuration (volume, layers, connections, sensors, heating_rods).

- `gens` — list[str]: base generator names which are expanded into status/demand/supply keys.
- `NumberofTanks` — int: how many `tank` entries to create and manage.
- `TankbalanceSetup` — list[str]: pairings of tank ports that define flow balancing connections.

Primary attributes (selected)
- `generators` (dict): generator status/demand/supply keys like `'{gen}_status'`.
- `tank_connections` (dict): per-tank ports and temperature/flow keys (e.g., `'heat_in_T'`, `'heat_in_F'`).
- `tank_temps` (dict): sensor readings per tank layer.
- `sh_demand`, `dhw_demand`, `heat_demand` (float): loads in W (converted from kW inside `step`).
- `sh_supply`, `dhw_supply`, `heat_supply` (float): computed supply power in W.
- `hp_on_fraction`, `hp_cond_m` (float): heat pump on fraction and condenser mass flow.
- `timestamp` (datetime-like): current timestep for day/season logic.

Key methods
- `get_init_attrs()` — returns a flattened list of the object's attributes (helper utility).
- `step(time)` — main time-step update. It:
  - converts kW inputs to W,
  - sets season/day flags based on `self.timestamp`,
  - Uses the `logic` dict to determine the operation status and demand of the generators.  
  - calls `calc_heat_supply` to compute flows/temps for SH/DHW,
  - computes heating rod power requirements and adjusts generator demands/status,
  - performs tank balancing flows for multi-tank setups.


## TCValve

Purpose
: A simplified 3-way temperature-controlled mixing valve used to combine two tank flows (hot and cold) to achieve target supply temperature.

Constructor
: `valve = TCValve(max_flow)`

Method
- `get_flows(Thot, Tcold, T, flow, dT)`
  - Inputs:
    - `Thot`, `Tcold` — temperatures of hot and cold tanks (°C or None)
    - `T` — requested supply temperature (°C)
    - `flow` — requested total flow (kg/s or same units used by the controller)
    - `dT` — delta between supply and return
  - Returns: `f_hot, f_cold, T_sup` — flows from hot and cold source and achieved supply temperature.

Behavior highlights
- If either tank is warmer than `T` the valve can prioritize that tank and reduce total flow if necessary.
- The valve enforces a `maxflow` per source and will limit flows if they exceed that value.

## idealHeatRod

Purpose
: Very simple ideal electric heating rod model used to calculate backup power and flow to reach a setpoint.

Constructor
: `rod = idealHeatRod(setpoint=None, returntemp=None)`

Method
- `step(temp, demand, sup_setTemp=None, ret_setTemp=None)`
  - `temp` — current outlet temperature (°C)
  - `demand` — required thermal energy for current timestep (kW as passed into the controller)
  - `sup_setTemp`, `ret_setTemp` — supply/return setpoints (°C). If not provided, the object's `dhw_sp` and `rT` are used.
  - Returns: `(flow, P)` where `flow` is the mass flow required and `P` is instantaneous heater power in W.

Notes
- If setpoint/return temperature are missing the `IncompleteConfigError` is raised.
- The model assumes cp = 4184 J/(kg·K) and 1 L = 1 kg for volumes.

## Exception

- `IncompleteConfigError` — used to signal missing configuration for the heating rod's temperature targets.


## Usage examples

Minimal example (constructing controller and performing one step):

```python
from src.models.controller import Controller
from datetime import datetime

params = {
        "T_dhw_sp": 65,
        "dhw_Tdelta" : 15,
        "T_dhw_buffer": 5,
        "control_strategy": "1",
        "supply_config": "4-runner",
        "Ideal_hr_mode" :"off",
        "sh_out" : "tank1.heat_out2",
        "sh_out2" : "tank2.heat_out2",
        "dhw_out" : "tank2.heat_out",
        "sh_ret" : "tank0.heat_in",
        "dhw_ret" : "tank2.heat_in",
        "gens" : ["hp", "boiler"],
        "NumberofTanks" : 3,
        "TankbalanceSetup" : ["tank0.heat_out:tank1.hp_out", "tank1.heat_out:tank2.hp_out"]
    }

ctrl = Controller(params)
ctrl.timestamp = datetime.now()
ctrl.sh_demand = 2.0  # kW
ctrl.dhw_demand = 0.5 # kW
ctrl.step(0)
print(ctrl.sh_supply, ctrl.dhw_supply)
```

## Developer notes & assumptions

- Many defaults and helper functions live outside this module (for example `helpers.get_nested_attr` and `helpers.set_nested_attr`). The doc assumes those helpers behave as implied by their names.
- Units: controller expects some user inputs in kW (converted to W inside `step`) and temperatures in °C. 

