# Gas Boiler — Configuration Guide

## Overview

The boiler model simulates a staged gas boiler that selects a thermal output level from a set of defined capacity stages based on the current heat demand. It computes either the outlet temperature or the mass flow rate at each timestep, and optionally models a startup transient which is a period after ignition during which output ramps up to its target stage. Fuel consumption is also tracked based on the configured efficiency.

## Parameters

### Required

`efficiency` and an output mode (`set_temp` or `set_flow`) are always required. For power capacity, choose one of the two options below.

| Parameter | Type | Unit | Description |
|---|---|---|---|
| `efficiency` | float | — | Nominal fuel-to-heat efficiency. Must be a value between 0 and 1. |
| `set_temp` | float | °C | Fixed outlet temperature. The model computes the mass flow rate needed to deliver the current power at this temperature. |
| `set_flow` | float | kg/s | Fixed mass flow rate. The model computes the outlet temperature from the current power and this flow rate. |

> If both `set_temp` and `set_flow` are provided, `set_temp` takes precedence and `set_flow` is ignored.

**Power capacity — Option A (explicit stages):**

| Parameter | Type | Unit | Description |
|---|---|---|---|
| `heat_out_caps` | list[float] | W | Explicit list of available thermal output stages sorted in ascending order, e.g. `[0, 5000, 10000]`. The boiler picks the smallest stage that meets the current demand, or the largest stage if demand exceeds all stages. |

**Power capacity — Option B (nominal + fractions):**

| Parameter | Type | Unit | Description |
|---|---|---|---|
| `nom_P_th` | float | W | Nominal (maximum) thermal power output. |
| `op_stages` | list[float] | — | Relative stage fractions as values between 0 and 1 sorted in ascending order, e.g. `[0, 0.5, 1.0]`. Combined with `nom_P_th` to produce the actual stage list. Defaults to `[0, 1]` if not provided. |

> If both `heat_out_caps` and `nom_P_th` + `op_stages` are provided, `heat_out_caps` takes precedence and the other two are ignored.

### Optional

| Parameter | Type | Unit | Default | Description |
|---|---|---|---|---|
| `heating_value` | float | J/g | `10833.3` | Fuel heating value. Default is for natural gas. Set this if using a different fuel. |
| `cp` | float | J/kg.K | `4187` | Specific heat capacity of the working fluid. Default is water. Set this if using a different fluid. |
| `startup_limit` | float | min | — | Duration of the startup transient in minutes. When set alone (no coefficients), the built-in linear ramp is used. When set with `startup_coeff` or `startup_eta_coeff`, your custom polynomial is used instead. See Startup behaviour below. |
| `startup_coeff` | list[float] | — | — | Polynomial coefficients for power output during startup. See Startup behaviour below. |
| `startup_eta_coeff` | list[float] | — | — | Polynomial coefficients for efficiency during startup. See Startup behaviour below. |

> If `startup_limit` is not set, the boiler switches instantly to its target stage with no startup transient.

## Startup behaviour

If `startup_limit` is not configured, the boiler switches instantly to its target power stage when turned on. When `startup_limit` is set, a startup transient is applied: by default a built-in linear ramp is used — power ramps from 0 to the target stage and efficiency from 90% of nominal up to nominal, both over the `startup_limit` duration. If you also provide `startup_coeff` or `startup_eta_coeff`, your coefficients override the default for the respective quantity.


### How the polynomial works

The model evaluates a polynomial in uptime (minutes since last ignition):

```
P(t) = a0 + a1·t + a2·t² + ...
```

Where `t` is uptime in minutes and the result is in **kW**. The coefficients are provided as a list ordered from the constant term upward: `[a0, a1, a2, ...]`.

For example, a linear ramp from 0 to 10 kW over 5 minutes:

```json
"startup_coeff": [0.0, 2.0],
"startup_limit": 5.0
```

This gives `P(t) = 0 + 2·t`, reaching 10 kW at t = 5 min.

The same structure applies to `startup_eta_coeff` for efficiency:

```json
"startup_eta_coeff": [0.7, 0.04],
"startup_limit": 5.0
```

This gives `eta(t) = 0.7 + 0.04·t`, reaching 0.9 at t = 5 min.

> `startup_eta_coeff` can be used independently of `startup_coeff`. Either way, `startup_limit` must be set.

## Reference

### Gboiler

`boiler = Gboiler(params)`

**Output attributes**

- `P_th` — float [W]: thermal power output in the current timestep.
- `temp_out` — float [°C]: outlet temperature. Equals `set_temp` when `set_temp` is used; computed from `P_th` and `mdot` when `set_flow` is used.
- `mdot` — float [kg/s]: mass flow rate. Computed from `P_th` and temperature rise when `set_temp` is used; equals `set_flow` when `set_flow` is used.
- `fuel` — float: fuel consumed in the current timestep. Units follow the configured `heating_value`.
- `eta` — float: current efficiency. During startup this follows `startup_eta_coeff` if provided, or the built-in linear ramp if only `startup_limit` is set; otherwise equals `efficiency`.
- `uptime` — float [min]: time elapsed since the last ignition. Resets to 0 when the boiler turns off.

**Methods**

- `step(time)` — advances the boiler by one timestep. Selects the appropriate power stage, applies startup behaviour if configured, and computes `temp_out`, `mdot`, and `fuel`.
- `validate_params(params)` — validates the configuration before the simulation starts. Raises `IncompleteConfigError` if required parameters are missing or inconsistent.

## Exception

- `IncompleteConfigError` — raised by `validate_params` if a required parameter is missing or a cross-field constraint is not met.

## Sample parameters

Minimal setup — instant switch, no startup transient:

```python
params = {
    "efficiency": 0.9,
    "set_flow": 4,
    "heat_out_caps": [0, 5000, 10000]
}
```

Using `nom_P_th` + `op_stages` with the default linear startup:

```python
params = {
    "efficiency": 0.9,
    "set_temp": 80,
    "nom_P_th": 10000,
    "op_stages": [0, 0.5, 1.0],
    "startup_limit": 5.0
}
```

With custom startup coefficients:

```python
params = {
    "efficiency": 0.92,
    "set_temp": 80,
    "heat_out_caps": [0, 5000, 10000],
    "startup_limit": 11,
    "startup_coeff": [-2.63, 3.9, 0.57],
    "startup_eta_coeff": [0.7, 0.04]
}
```