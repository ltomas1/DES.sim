# PV — Configuration Guide

## Overview

The PV model simulates photovoltaic power generation using the `pvlib` library. It computes the electrical power output over a full year using either a local measured weather dataset (CSV) or hourly data fetched automatically from the PVGIS API. The model supports multiple solar arrays with independent tilts and azimuths, and can operate either as a standalone CSV generator or as a direct Mosaik plug-in.

## Operation Modes

The model behavior is dictated by the `op_mode` parameter:

- **Standalone (`"standalone"`)**: Runs the full annual simulation upon initialization, resamples the data to 15-minute intervals, and exports a CSV file containing the `Power[w]` column. This file can be read by `mosaik-csv`.
- **Mosaik Plug-in (`"mosaik"`)**: Utilizes the `PVSimulator` class to wrap the model in Mosaik's API, allowing it to step through the pre-calculated weather dataframe dynamically during a co-simulation. 
*(Note: This mode is currently still not implemented).*

## Data Sources

The model determines irradiation and weather data using one of two methods:

1. **Measured Data**: If `irradiation_data` is provided, the model reads the local CSV file. It expects GHI, DNI, Air Temperature, and Wind Speed, and calculates DHI internally. 
2. **PVGIS API**: If `irradiation_data` is omitted, the model automatically fetches Plane-of-Array (POA) hourly weather data directly from the PVGIS API based on the system's coordinates and array configurations.

## Parameters

### Required

| Parameter | Type | Unit | Description |
|---|---|---|---|
| `calc_mode` | str | — | Calculation mode. Currently, only "simple" is supported. |
| `nom_power` | float | W | Requested nominal PV power for scaling the array output. Must be > 0. |
| `coordinates` | list | — | Setup location: `[latitude, longitude, "name", altitude, "timezone"]`. (e.g., `[49.1, 8.5, "Karlsruhe", 110, "Etc/GMT-1"]`) |
| `op_year` | int | — | Operating year for the simulation. Note: PVGIS data is currently capped at 2023. Must match the simulation start year setup in `main_sim.py`. |
| `op_mode` | str | — | `"standalone"` is currently the only option |

### Optional

| Parameter | Type | Unit | Default | Description |
|---|---|---|---|---|
| `irradiation_data` | str | — | — | Path to the measured weather CSV. If omitted, PVGIS retrieval is used. |
| `pv_arrays` | list[dict] | — | `[{tilt: latitude from coordinates, azimuth: 180}]` | List of array configurations defining the tilt and azimuth of each PV plane. (Azimuth: 0=North, 90=East, 180=South). |
| `surface_tilt` | float | deg | latitude from coordinates | Fallback tilt angle (0 to 360). |
| `surface_azimuth` | float | deg | 180 | Fallback azimuth (0 to <360, where 180 is South). |

## Array Configuration

If the PV system consists of multiple orientations (e.g., an East-West roof), define them using the `pv_arrays` list. Each dictionary in the list must contain a `tilt` and an `azimuth`. The total nominal power will be divided equally across the defined arrays.

```json
"pv_arrays": [
    {"tilt": 30, "azimuth": 90},  
    {"tilt": 30, "azimuth": 270}  
]
```

## Reference

### PV Model
`pv_model = PV(params)`

**Attributes**
- `weather` — pandas.DataFrame: Contains the timestamps and the generated `Power[w]` column.
- `output_path` — str: Absolute path to the generated output CSV file (in standalone mode).

**Methods**
- `sim()` — Returns the file path of the generated CSV.
- `step(time)` — Resamples the dataframe based on `step_size` and time. 
- `validate_params(params)` — Validates parameter types and cross-field logic against predefined rules.

### Exceptions
- `ValueError` — Raised by `validate_params` if parameters are missing, of the wrong type, or if `op_year` does not match the year setup in the `main_sim.py`.

## Sample parameters

```json
"pv": {
  "calc_mode": "simple",
  "nom_power": 70000,
  "coordinates": [49.1, 8.5, "Stutensee", 110, "Etc/GMT-1"],
  "irradiation_data": "data/inputs/2025-04-07-Project1-weather.csv",
  "op_year": 2022,
  "op_mode": "standalone",
  "pv_arrays": [
    {"tilt": 30, "azimuth": 281},
    {"tilt": 30, "azimuth": 101}
  ]
}