from __future__ import annotations

"""Preprocessing helper for `visu_v2.ipynb`.

This module is intentionally opinionated: it provides a single "magic" entrypoint
(`prepare_visu_v2`) that loads simulation outputs and returns a dict of notebook-ready
artifacts.

Behavior invariants (do not change without updating the notebook expectations):
- PV "latest" selection uses `os.path.getctime`.
- `untranslated_columns` is a sorted `np.ndarray` (from `np.setdiff1d`).
- `df_monthly` uses `df.resample("M").sum() / 4` (kept as-is).
- Electrical allocation order is defined by the insertion order of detected users/producers.
"""

import glob
import json
import os
import datetime as _dt
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np
import pandas as pd


DES_DATE_INDEX_COL = "date"
PV_INDEX_COL = "Unnamed: 0"
INPUT_TIME_COL = "Time"

SECONDS_PER_HOUR = 3600.0
CP_WATER_J_PER_KG_K = 4184.0

DEFAULT_ETA_CHP = 0.5
DEFAULT_ETA_BOILER = 0.8

HEATING_ROD_ELECTRIC_EFF = 0.98

# Columns that existing plots reference directly (KeyError if missing).
REQUIRED_PLOT_COLUMNS = [
    "HP_Q_Supplied",
    "CHP_P_th",
    "Boiler_P_th",
    "HWT2_hr1_P_th",
    "HWT2_sensor0_T",
    "HWT2_sensor2_T",
    "HWT1_sensor2_T",
    "Heat Demand [KW]",
]

COLUMN_TRANSLATION_BASE: Dict[str, str] = {
    "Power[w]": "PV_P[W]",
    "CSV-0.DNI_0-DNI": "DNI",
    "CSV-1.HEATLOAD_0-T_amb": "T_amb",
    "CSV-1.HEATLOAD_0-Heat Demand [kW]": "Heat Demand [KW]",
    "CHPSim-0.CHP_0-eff_el": "CHP_eff",
}

TANK_SUFFIX_TRANSLATIONS: Dict[str, str] = {
    "sensor_00.T": "sensor0_T",
    "sensor_01.T": "sensor1_T",
    "sensor_02.T": "sensor2_T",
    "heat_out.T": "heatout_T",
    "heat_out.F": "heatout_F",
    "heat_out2.T": "heatout2_T",
    "heat_out2.F": "heatout2_F",
    "hp_in.T": "hp_in_T",
    "hp_in.F": "hp_in_F",
    "hp_out.T": "hp_out_T",
    "hp_out.F": "hp_out_F",
    "heat_in.T": "heatin_T",
    "heat_in.F": "heatin_F",
    "T_mean": "Tmean",
    "hr_1.P_th": "hr1_P_th",
}

THERMAL_COLOR_MAP: Dict[str, str] = {
    "Natural Gas": "rgba(255, 140, 0, 0.7)",
    "CHP": "rgba(255, 49, 20, 0.7)",
    "Gas Boiler": "rgba(255, 0, 0, 0.7)",
    "Heat Pump": "rgba(255, 0, 75, 0.7)",
    "Source": "rgba(0, 180, 138, 0.7)",
    "Heating Rods": "rgba(255, 197, 41, 0.7)",
    "Heat Deficit": "crimson",
    "DHW": "rgba(109, 0, 250, 0.7)",
    "SH": "rgba(109, 0, 250, 0.7)",
    "DHN": "rgba(109, 0, 255, 0.7)",
    "Storage Loss": "rgba(130, 0, 3, 0.56)",
}


# Defaults for the "Generic Energy Balance Sankey" notebook cell.
# Keep these in sync with the notebook to avoid behavior changes.
GENERIC_ENERGY_SANKEY_NODE_CONFIG: Dict[str, Tuple[float, float, str]] = {
    # --- Layer 0: Sources (Left) ---
    "Natural Gas": (0, 0.1, "darkorange"),
    "Source": (0, 0.45, "rgba(0, 200, 150, 0.8)"),
    "PV": (0, 0.6, "yellowgreen"),
    "Grid": (0, 0.9, "gold"),
    "Unused Surplus": (0, 0.9, "gray"),
    # --- Layer 0.5: sources/Components (Before-Middle-Left) ---
    "CHP": (0.5, 0.3, "brown"),
    # --- Layer 1: Components (Middle-Left) ---
    "Gas Boiler": (1, 0.1, "red"),
    "Heat Pump": (1, 0.5, "rgba(217, 104, 0, 1)"),
    "Heating Rods": (1, 0.7, "magenta"),
    "Heating": (1, 0.8, "aqua"),
    "Heat Deficit": (1, 0.9, "crimson"),
    # --- Layer 2: Storage (Middle-Right) ---
    "Buffer Tank": (2, 0.35, "rgba(0, 0, 189, 0.8)"),
    "Battery": (2, 0.8, "purple"),
    # --- Layer 3: Consumers (Right) ---
    "DHW": (3, 0.1, "teal"),
    "SH": (3, 0.35, "thistle"),
    "DHN": (3, 0.6, "green"),
    "Storage Loss": (3, 0.55, "rgba(69, 0, 0, 0.76)"),
    "Grid Feed-In": (3, 0.65, "rgba(0, 168, 0, 0.5)"),
    "Household Electricity": (3, 0.9, "yellow"),
}

GENERIC_ENERGY_SANKEY_LAYER_POSITIONS: Dict[float, float] = {
    0: 0.001,
    0.5: 0.15,
    1: 0.33,
    1.5: 0.55,
    2: 0.66,
    3: 0.999,
}


def prepare_visu_v2(
    *,
    project_root: Optional[Path | str] = None,
    des_csv_path: Optional[Path | str] = None,
    pv_output_dir: Optional[Path | str] = None,
    input_csv_path: Optional[Path | str] = None,
    params_json_path: Optional[Path | str] = None,
    step_size: Optional[float] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Prepare all data structures that `visu_v2.ipynb` expects.

    This is intended to be a preprocessing entry point.
    Keep the plotting notebook unchanged; only replace its prep section.

    Pipeline stages:
    - Stage 1: resolve paths + validate inputs
    - Stage 2: load raw inputs (DES, PV, demand, params)
    - Stage 3: prepare frames (merge PV, translate columns, coerce numeric, monthly)
    - Stage 4: compute outputs (energies + electrical/thermal Sankey links)
    """

    # Stage 1: resolve paths + validate
    paths = _stage1_resolve_paths(
        project_root=project_root,
        des_csv_path=des_csv_path,
        pv_output_dir=pv_output_dir,
        input_csv_path=input_csv_path,
        params_json_path=params_json_path,
    )

    # Stage 2: load raw inputs
    loaded = _stage2_load_inputs(paths)

    # Stage 3: prepare frames
    prepared = _stage3_prepare_frames(loaded)

    # Stage 4: compute energies + Sankey links
    computed = _stage4_compute_outputs(df=prepared["df"], input_df=loaded["input_df"], params=loaded["params"], step_size=step_size)

    # Convenience: expose time coverage for notebook use (e.g. days simulated)
    if prepared["df"].empty or not isinstance(prepared["df"].index, pd.DatetimeIndex):
        time_coverage: Dict[str, Any] = {
            "start": None,
            "end": None,
            "rows": int(prepared["df"].shape[0]),
            "duration": None,
            "duration_days": None,
            "dt_mode_s": None,
            "dt_min_s": None,
            "dt_max_s": None,
        }
    else:
        start = prepared["df"].index.min()
        end = prepared["df"].index.max()
        duration = end - start
        duration_days = duration.total_seconds() / 86400.0 if pd.notna(duration) else None

        if len(prepared["df"].index) >= 2:
            diffs = prepared["df"].index.to_series().diff().dropna()
            diffs_s = diffs.dt.total_seconds().astype("float")
            dt_min_s = float(diffs_s.min()) if not diffs_s.empty else None
            dt_max_s = float(diffs_s.max()) if not diffs_s.empty else None
            try:
                dt_mode_s = float(diffs_s.round(6).mode().iloc[0]) if not diffs_s.empty else None
            except Exception:
                dt_mode_s = None
        else:
            dt_mode_s = dt_min_s = dt_max_s = None

        time_coverage = {
            "start": start,
            "end": end,
            "rows": int(prepared["df"].shape[0]),
            "duration": duration,
            "duration_days": duration_days,
            "dt_mode_s": dt_mode_s,
            "dt_min_s": dt_min_s,
            "dt_max_s": dt_max_s,
        }

    if verbose:
        _print_run_report(
            root=paths["root"],
            des_csv=paths["des_csv"],
            latest_pv_file=loaded["latest_pv_file"],
            input_csv=paths["input_csv"],
            params_json=paths["params_json"],
            resolved_step_size=computed["resolved_step_size"],
            df=prepared["df"],
            untranslated_columns=prepared["untranslated_columns"],
            energies=computed["energies"],
            init_energy=computed["init_energy"],
            end_energy=computed["end_energy"],
            elec_links_df=computed["elec_links_df"],
            elec_links=computed["elec_links"],
            thermal_links=computed["thermal_links"],
            final_links=computed["final_links"],
        )

    return {
        "step_size": computed["resolved_step_size"],
        "df": prepared["df"],
        "generic_energy_sankey": build_sankey_inputs(computed["final_links"]),
        "electric_sankey": build_sankey_inputs(computed["elec_links"]),
        "params": loaded["params"],
        "params_hp": loaded["params_hp"],
        "params_ctrl": loaded["params_ctrl"],
        "params_hwt": loaded["params_hwt"],
        "params_chp": loaded["params_chp"],
        "params_boiler": loaded["params_boiler"],
        "time_coverage": time_coverage,
        "days_simulated": time_coverage.get("duration_days"),
    }


def _infer_project_root() -> Path:
    """Infer repo root robustly when called from a notebook.

    We prefer the first parent that contains both `data/` and `src/`.
    """

    this_file = Path(__file__).resolve()
    for parent in this_file.parents:
        if (parent / "data").exists() and (parent / "src").exists():
            return parent
    # Fallback: src/utils/<file>.py -> parents[2] is usually repo root
    return this_file.parents[2]


def _find_latest_csv(directory: Path) -> Path:
    files = glob.glob(str(directory / "*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in: {directory}")
    # Keep behavior identical to notebook: newest by creation time
    return Path(max(files, key=os.path.getctime)).resolve()


def _resolve_step_size(step_size: Optional[float]) -> float:
    if step_size is not None:
        return float(step_size)

    # TODO(user): Make step size handling more explicit/configurable.
    # For now, match notebook behavior by trying to import main_sim.
    try:
        import main_sim  # type: ignore

        return float(main_sim.STEP_SIZE)
    except Exception:
        pass

    try:
        from src import main_sim  # type: ignore

        return float(main_sim.STEP_SIZE)
    except Exception:
        raise RuntimeError(
            "Could not resolve STEP_SIZE. Pass step_size=... explicitly or "
            "ensure main_sim is importable (as in the notebook)."
        )


def _merge_pv_and_dedup(df: pd.DataFrame, pv_df: pd.DataFrame) -> pd.DataFrame:
    # Merge PV output onto the DES output (index-aligned time series)
    merged = df.merge(pv_df, left_index=True, right_index=True, how="left")

    # 1. CLEAN UP PV DUPLICATES (Fixes _x and _y)
    # If we have _x and _y columns, keep _x (usually the main file) and drop _y
    cols_to_drop = [c for c in merged.columns if c.endswith("_y")]
    if cols_to_drop:
        merged.drop(columns=cols_to_drop, inplace=True)

    # Rename _x columns back to normal (remove the suffix)
    rename_map = {c: c.replace("_x", "") for c in merged.columns if c.endswith("_x")}
    if rename_map:
        merged.rename(columns=rename_map, inplace=True)

    return merged


def _build_column_translation(df_columns: Iterable[str]) -> Dict[str, str]:
    columnname: Dict[str, str] = dict(COLUMN_TRANSLATION_BASE)

    # 3. The Generic Loop
    for col in df_columns:
        # Skip if already renamed
        if col.startswith("HWT") or col.startswith("CHP_") or col.startswith("Boiler_") or col.startswith(
            "HP_"
        ):
            continue

        if "HotWaterTankSim" in col:
            tank_id = col.split(".")[0].split("-")[-1]
            for ugly_end, clean_end in TANK_SUFFIX_TRANSLATIONS.items():
                if col.endswith(ugly_end):
                    columnname[col] = f"HWT{tank_id}_{clean_end}"
                    break

        elif "HeatPump" in col:
            suffix = col.split("-")[-1]
            columnname[col] = f"HP_{suffix}"

        elif "Boiler" in col:
            suffix = col.split("-")[-1]
            columnname[col] = f"Boiler_{suffix}"

        elif "CHP" in col and col not in columnname:
            suffix = col.split("-")[-1]
            columnname[col] = f"CHP_{suffix}"

        elif "Controller" in col:
            suffix = col.split("-")[-1]
            if "." in suffix:
                suffix = suffix.split(".")[-1]
            columnname[col] = suffix

    return columnname


def _apply_column_translation(df: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray]:
    oldcolumns = df.columns
    columnname = _build_column_translation(oldcolumns)

    column_translate = np.asarray(list(columnname.keys()))
    untranslated = np.setdiff1d(oldcolumns, column_translate)

    df = df.rename(columns=columnname)

    return df, untranslated


def _print_run_report(
    *,
    root: Path,
    des_csv: Path,
    latest_pv_file: Path,
    input_csv: Path,
    params_json: Path,
    resolved_step_size: float,
    df: pd.DataFrame,
    untranslated_columns: np.ndarray,
    energies: Dict[str, float],
    init_energy: float,
    end_energy: float,
    elec_links_df: pd.DataFrame,
    elec_links: Dict[str, list],
    thermal_links: Dict[str, list],
    final_links: Dict[str, list],
) -> None:
    print("\n=== visu_v2 preprocessing report ===")

    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    step = 1024.0

    # FILES
    print("\nFILES")
    for label, p in [
        ("project_root", root),
        ("DES CSV", des_csv),
        ("PV CSV (latest)", latest_pv_file),
        ("Input demand CSV", input_csv),
        ("Params JSON", params_json),
    ]:
        path = Path(p)
        try:
            stat = path.stat()
            mtime = _dt.datetime.fromtimestamp(stat.st_mtime)
            size = int(stat.st_size)
        except Exception:
            mtime = None
            size = None

        if mtime is None:
            mtime_str = "?"
        else:
            mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S")

        if size is None:
            size_str = "?"
        else:
            size_f = float(size)
            size_str = "?"
            for unit in units:
                if size_f < step:
                    size_str = f"{size_f:.1f} {unit}" if unit != "B" else f"{int(size_f)} {unit}"
                    break
                size_f /= step
            if size_str == "?":
                size_str = f"{size_f:.1f} PiB"

        print(f"- {label}: {path}")
        print(f"  mtime: {mtime_str} | size: {size_str}")
    print(f"- step_size: {resolved_step_size} s")

    # TIME COVERAGE
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        cov: Dict[str, Any] = {
            "start": None,
            "end": None,
            "rows": int(df.shape[0]),
            "duration": None,
            "duration_days": None,
            "dt_mode_s": None,
            "dt_min_s": None,
            "dt_max_s": None,
        }
    else:
        start = df.index.min()
        end = df.index.max()
        duration = end - start
        duration_days = duration.total_seconds() / 86400.0 if pd.notna(duration) else None

        if len(df.index) >= 2:
            diffs = df.index.to_series().diff().dropna()
            diffs_s = diffs.dt.total_seconds().astype("float")
            dt_min_s = float(diffs_s.min()) if not diffs_s.empty else None
            dt_max_s = float(diffs_s.max()) if not diffs_s.empty else None
            try:
                dt_mode_s = float(diffs_s.round(6).mode().iloc[0]) if not diffs_s.empty else None
            except Exception:
                dt_mode_s = None
        else:
            dt_mode_s = dt_min_s = dt_max_s = None

        cov = {
            "start": start,
            "end": end,
            "rows": int(df.shape[0]),
            "duration": duration,
            "duration_days": duration_days,
            "dt_mode_s": dt_mode_s,
            "dt_min_s": dt_min_s,
            "dt_max_s": dt_max_s,
        }

    print("\nTIME COVERAGE")
    print(f"- rows: {cov['rows']} | columns: {df.shape[1]}")
    print(f"- start: {cov['start']} | end: {cov['end']}")
    if cov["duration"] is not None:
        days = cov.get("duration_days")
        days_str = f"{days:.2f} days" if isinstance(days, (int, float)) else "? days"
        print(f"- duration: {cov['duration']} ({days_str})")
    

    # TRANSLATION
    print("\nCOLUMN TRANSLATION")
    untranslated_count = int(len(untranslated_columns))
    print(f"- untranslated columns: {untranslated_count}")
    if untranslated_count > 0:
        sample = list(untranslated_columns[:10])
        print(f"{sample}")

    # PLOT INPUTS
    missing = [c for c in REQUIRED_PLOT_COLUMNS if c not in df.columns]
    if missing:
        print("\nPLOT INPUTS")
        print(f"- missing plot columns ({len(missing)}): {missing}")

    # ELECTRICAL (report is based on links that actually exist)
    print("\nELECTRICAL (Sankey)")
    elec_nodes = set()
    for k in elec_links.keys():
        src, tgt = k.split(":")
        elec_nodes.add(src)
        elec_nodes.add(tgt)
    print(f"- active links: {len(elec_links)} | link columns (df): {elec_links_df.shape[1]}")
    if elec_nodes:
        print(f"- nodes: {sorted(elec_nodes)}")
    if elec_links:
        top = sorted(elec_links.items(), key=lambda kv: float(kv[1][0]), reverse=True)[:8]
        print("- top links:")
        for name, (val, _color) in top:
            value_wh = float(val)
            abs_val = abs(value_wh)
            if abs_val >= 1_000_000:
                value_str = f"{value_wh/1_000_000:.3f} MWh"
            elif abs_val >= 1_000:
                value_str = f"{value_wh/1_000:.3f} kWh"
            else:
                value_str = f"{value_wh:.1f} Wh"
            print(f"  {name}: {value_str}")

    # THERMAL
    print("\nTHERMAL (Sankey)")
    print(f"- thermal links: {len(thermal_links)}")
    # show top thermal links for quick sanity
    if thermal_links:
        top_t = sorted(thermal_links.items(), key=lambda kv: float(kv[1][0]), reverse=True)[:8]
        print("- top links:")
        for name, (val, _color) in top_t:
            value_wh = float(val)
            abs_val = abs(value_wh)
            if abs_val >= 1_000_000:
                value_str = f"{value_wh/1_000_000:.3f} MWh"
            elif abs_val >= 1_000:
                value_str = f"{value_wh/1_000:.3f} kWh"
            else:
                value_str = f"{value_wh:.1f} Wh"
            print(f"  {name}: {value_str}")

    # ENERGY SUMMARY (existing accounting)
    print("\nENERGY SUMMARY")
    abs_val = abs(init_energy)
    if abs_val >= 1_000_000:
        init_str = f"{init_energy/1_000_000:.3f} MWh"
    elif abs_val >= 1_000:
        init_str = f"{init_energy/1_000:.3f} kWh"
    else:
        init_str = f"{init_energy:.1f} Wh"

    abs_val = abs(end_energy)
    if abs_val >= 1_000_000:
        end_str = f"{end_energy/1_000_000:.3f} MWh"
    elif abs_val >= 1_000:
        end_str = f"{end_energy/1_000:.3f} kWh"
    else:
        end_str = f"{end_energy:.1f} Wh"

    print(f"- init storage: {init_str}")
    print(f"- end storage:  {end_str}")
    # Keep a stable order for readability
    keys_order = [
        "chp_supply",
        "chp_el_supply",
        "chp_gas_consumption",
        "boiler_supply",
        "boiler_gas_consumption",
        "hp_req",
        "hp_evap",
        "hp_supply",
        "hrods_supply",
        "pv_supply",
        "sh_supply",
        "dhw_supply",
        "heat_supply",
        "heat_demand",
        "ideal_supply",
        "total_supply",
    ]
    for k in keys_order:
        if k in energies:
            value_wh = float(energies[k])
            abs_val = abs(value_wh)
            if abs_val >= 1_000_000:
                value_str = f"{value_wh/1_000_000:.3f} MWh"
            elif abs_val >= 1_000:
                value_str = f"{value_wh/1_000:.3f} kWh"
            else:
                value_str = f"{value_wh:.1f} Wh"
            print(f"- {k}: {value_str}")

    # FINAL
    print("\nFINAL")
    print(f"- final_links: {len(final_links)}")
    print("=== end report ===\n")


def _compute_storage_energies(
    df: pd.DataFrame,
    *,
    params_hwt: Dict[str, Any],
    params_ctrl: Dict[str, Any],
    init_vals_tanks: Dict[str, Any],
) -> Tuple[float, float]:
    # Use values from the loaded JSON params (safer than relying on main_sim)
    volume = params_hwt["volume"]
    cp_water = CP_WATER_J_PER_KG_K  # J/kg*K
    ref_temp = 20 # °C

    # Sum (Volume * Cp * (T_avg - T_ref)) for ALL tanks found in JSON
    init_temps_sum = 0.0
    num_tanks_init = 0

    for _, tank_data in init_vals_tanks.items():
        avg_T = float(np.mean(tank_data["layers"]["T"]))
        init_temps_sum += avg_T
        num_tanks_init += 1

    # Calculate Total Initial Energy (Wh)
    init_energy = (volume * cp_water * (init_temps_sum - (num_tanks_init * ref_temp))) / 3600

    # Find all columns like 'HWT0_Tmean', 'HWT1_Tmean' etc.
    tmean_cols = [c for c in df.columns if c.endswith("_Tmean")]
    final_temps_sum = float(df[tmean_cols].iloc[-1].sum()) if tmean_cols else 0.0

    # Calculate Total Final Energy (Wh)
    end_energy = (volume * cp_water * (final_temps_sum - (len(tmean_cols) * ref_temp))) / 3600

    return init_energy, end_energy


def _get_energy(col_series: pd.Series, *, step_size: float) -> float:
    # Helper function
    # Sums power (Watts) * time (hours) = Energy (Wh)
    return float(col_series.sum()) * step_size / SECONDS_PER_HOUR


def _compute_energies(df: pd.DataFrame, *, params: Dict[str, Any], step_size: float) -> Tuple[Dict[str, float], float, float]:
    params_ctrl = params.get("ctrl") or {}
    params_hwt = params.get("tank") or {}
    init_vals_tanks = params.get("init_vals_tank") or {}

    params_chp = params.get("params_chp") or {}
    params_boiler = params.get("params_boiler") or {}

    init_energy, end_energy = _compute_storage_energies(
        df,
        params_hwt=params_hwt,
        params_ctrl=params_ctrl,
        init_vals_tanks=init_vals_tanks,
    )

    # Define Efficiencies (taken from input params dict)
    # If no efficiency is defined by the model, we fall back to assumed values.
    eta_chp = float(params_chp.get("efficiency", DEFAULT_ETA_CHP))
    eta_boiler = float(params_boiler.get("efficiency", DEFAULT_ETA_BOILER))

    energies: Dict[str, float] = {
        "chp_supply": 0.0,
        "chp_el_supply": 0.0,
        "chp_gas_consumption": 0.0,
        "boiler_supply": 0.0,
        "boiler_gas_consumption": 0.0,
        "hp_req": 0.0,
        "hp_evap": 0.0,
        "hp_supply": 0.0,
        "pv_supply": 0.0,
        "hrods_supply": 0.0,
        "sh_supply": 0.0,
        "dhw_supply": 0.0,
        "heat_supply": 0.0,
        "ideal_supply": 0.0,
        "heat_demand": 0.0,
    }

    # A. CHP (Look for ANY column starting with CHP_ and ending with P_th)
    chp_th_cols = [c for c in df.columns if c.startswith("CHP_") and c.endswith("P_th")]
    if chp_th_cols:
        energies["chp_supply"] = _get_energy(df[chp_th_cols[0]], step_size=step_size)
        if eta_chp > 0:
            energies["chp_gas_consumption"] = energies["chp_supply"] / eta_chp

    # Electrical output (P_el)
    chp_el_cols = [c for c in df.columns if c.startswith("CHP_") and "P_el" in c]
    if chp_el_cols:
        energies["chp_el_supply"] = _get_energy(df[chp_el_cols[0]], step_size=step_size)

    # B. Boiler
    boiler_cols = [c for c in df.columns if c.startswith("Boiler_") and c.endswith("P_th")]
    if boiler_cols:
        energies["boiler_supply"] = _get_energy(df[boiler_cols[0]], step_size=step_size)
        if eta_boiler > 0:
            energies["boiler_gas_consumption"] = energies["boiler_supply"] / eta_boiler

    # C. Heat Pump
    if "HP_P_Required" in df.columns:
        energies["hp_req"] = _get_energy(df["HP_P_Required"], step_size=step_size)
    if "HP_Q_evap" in df.columns:
        energies["hp_evap"] = abs(_get_energy(df["HP_Q_evap"], step_size=step_size))
    if "HP_Q_Supplied" in df.columns:
        energies["hp_supply"] = _get_energy(df["HP_Q_Supplied"], step_size=step_size)

    # D. Heating Rods (Generic Sum of ALL rods found)
    # Finds HWT2_hr1_P_th, HWT0_hr1_P_th, etc.
    rod_cols = [c for c in df.columns if "hr1_P_th" in c]
    if rod_cols:
        total_rod_power = df[rod_cols].sum(axis=1)
        energies["hrods_supply"] = _get_energy(total_rod_power, step_size=step_size)

    # E. Loads & PV (Using the mapped names)
    if "PV_P[W]" in df.columns:
        energies["pv_supply"] = _get_energy(df["PV_P[W]"], step_size=step_size)

    if "sh_supply" in df.columns:
        energies["sh_supply"] = _get_energy(df["sh_supply"], step_size=step_size)
    if "dhw_supply" in df.columns:
        energies["dhw_supply"] = _get_energy(df["dhw_supply"], step_size=step_size)

    if "heat_supply" in df.columns:
        energies["heat_supply"] = _get_energy(df["heat_supply"], step_size=step_size)

    if "heat_demand" in df.columns:
        energies["heat_demand"] = _get_energy(df["heat_demand"], step_size=step_size)

    if "IdealHrodsum" in df.columns:
        energies["ideal_supply"] = _get_energy(df["IdealHrodsum"], step_size=step_size)

    # Check differences in heat supply vs demand for 2-runner cases
    energies["total_supply"] = (
        energies["chp_supply"] + energies["boiler_supply"] + energies["hp_supply"] + energies["hrods_supply"]
    )

    return energies, init_energy, end_energy


def _build_electrical_links(df: pd.DataFrame, *, input_df: pd.DataFrame, step_size: float) -> Tuple[pd.DataFrame, Dict[str, list]]:
    # --- PREPARE DATA ---
    clone_df = df.copy(deep=True)

    # --- GENERIC PRODUCERS ---
    # Add here any new electrical producers you want to track
    producers: Dict[str, pd.Series] = {}
    if "PV_P[W]" in clone_df.columns:
        producers["PV"] = clone_df["PV_P[W]"]

    chp_el_col = [c for c in clone_df.columns if c.startswith("CHP_") and "P_el" in c]
    if chp_el_col:
        producers["CHP"] = clone_df[chp_el_col[0]]

    # --- GENERIC USERS (CONSUMERS) ---
    # Add here any new electrical users you want to track
    users: Dict[str, pd.Series] = {}
    if "Household_demand" in clone_df.columns:
        users["Household Electricity"] = clone_df["Household_demand"]
    elif "Electricity Demand [W]" in input_df.columns:
        users["Household Electricity"] = input_df["Electricity Demand [W]"]

    if "HP_P_Required" in clone_df.columns:
        users["Heat Pump"] = clone_df["HP_P_Required"]

    rod_cols = [c for c in clone_df.columns if "hr1_P_th" in c]
    if rod_cols:
        users["Heating Rods"] = clone_df[rod_cols].sum(axis=1) / HEATING_ROD_ELECTRIC_EFF

    # --- CREATE LINKS ---
    users_keys = list(users.keys())
    producers_keys = list(producers.keys())

    remaining_supply = {k: v.copy() for k, v in producers.items()}
    remaining_demand = {k: v.copy() for k, v in users.items()}

    elec_links_df = pd.DataFrame(index=clone_df.index)

    # Instead of looping through rows (35,000+), we loop through components
    # (only ~3-4). This preserves the priority order:
    # first user in list gets power first.
    for u_key in users_keys:
        for p_key in producers_keys:
            flow = np.minimum(remaining_demand[u_key], remaining_supply[p_key])
            col_name = f"{p_key}:{u_key}"
            elec_links_df[col_name] = flow
            remaining_demand[u_key] -= flow
            remaining_supply[p_key] -= flow

    for u_key in users_keys:
        import_needed = remaining_demand[u_key]
        if float(import_needed.sum()) > 0:
            elec_links_df[f"Grid:{u_key}"] = import_needed

    for p_key in producers_keys:
        export_possible = remaining_supply[p_key]
        if float(export_possible.sum()) > 0:
            elec_links_df[f"{p_key}:Grid Feed-In"] = export_possible

    raw_links: Dict[str, list] = {k: [_get_energy(elec_links_df[k], step_size=step_size), "springgreen"] for k in elec_links_df.columns}

    elec_links: Dict[str, list] = {k: v for k, v in raw_links.items() if v[0] > 0}

    return elec_links_df, elec_links


def _build_thermal_links(
    *,
    energies: Dict[str, float],
    init_energy: float,
    end_energy: float,
) -> Dict[str, list]:
    color_map = THERMAL_COLOR_MAP
    thermal_links: Dict[str, list] = {}

    # --- INPUTS (Producers -> Buffer) ---
    # We check the 'energies' dict we calculated in the math block
    if energies.get("chp_gas_consumption", 0.0) > 0:
        thermal_links["Natural Gas:CHP"] = [energies["chp_gas_consumption"], color_map["Natural Gas"]]
    if energies.get("chp_supply", 0.0) > 0:
        thermal_links["CHP:Buffer Tank"] = [energies["chp_supply"], color_map["CHP"]]

    if energies.get("boiler_gas_consumption", 0.0) > 0:
        thermal_links["Natural Gas:Gas Boiler"] = [energies["boiler_gas_consumption"], color_map["Natural Gas"]]
    if energies.get("boiler_supply", 0.0) > 0:
        thermal_links["Gas Boiler:Buffer Tank"] = [energies["boiler_supply"], color_map["Gas Boiler"]]

    if energies.get("hp_supply", 0.0) > 0:
        thermal_links["Source:Heat Pump"] = [energies.get("hp_evap", 0.0), color_map["Source"]]
        thermal_links["Heat Pump:Buffer Tank"] = [energies["hp_supply"], color_map["Heat Pump"]]

    if energies.get("hrods_supply", 0.0) > 0:
        thermal_links["Heating Rods:Buffer Tank"] = [energies["hrods_supply"], color_map["Heating Rods"]]

    if energies.get("ideal_supply", 0.0) > 0:
        thermal_links["Heat Deficit:Buffer Tank"] = [energies["ideal_supply"], color_map["Heat Deficit"]]

    # --- OUTPUTS (Buffer -> Consumers) ---
    if energies.get("dhw_supply", 0.0) > 0:
        thermal_links["Buffer Tank:DHW"] = [energies["dhw_supply"], color_map["DHW"]]

    if energies.get("sh_supply", 0.0) > 0:
        thermal_links["Buffer Tank:SH"] = [energies["sh_supply"], color_map["SH"]]

    if energies.get("heat_supply", 0.0) > 0:
        thermal_links["Buffer Tank:DHN"] = [energies["heat_supply"], color_map["DHN"]]


    # --- THE GENERIC LOSS CALCULATION ---
    # Loss = (Inputs + Init_Storage) - (Outputs + Final_Storage)
    total_input_energy = 0.0
    for key, val in thermal_links.items():
        if key.endswith(":Buffer Tank"):
            total_input_energy += val[0]
    total_input_energy += init_energy

    total_output_energy = 0.0
    for key, val in thermal_links.items():
        if key.startswith("Buffer Tank:"):
            total_output_energy += val[0]
    total_output_energy += end_energy

    energy_loss = total_input_energy - total_output_energy

    if energy_loss > 0:
        thermal_links["Buffer Tank:Storage Loss"] = [energy_loss, color_map["Storage Loss"]]

    return thermal_links


def build_sankey_inputs(
    final_links: Dict[str, list],
    *,
    node_config: Optional[Dict[str, Tuple[float, float, str]]] = None,
    layer_positions: Optional[Dict[float, float]] = None,
) -> Dict[str, Any]:
    # Mirror the notebook logic intentionally:
    # - Nodes are extracted from final_links keys, then sorted.
    # - Node indices are resolved via node_labels.index(...).
    # - Missing node config falls back to (layer=1.5, y=0.5, color='gray').
    node_config = node_config or GENERIC_ENERGY_SANKEY_NODE_CONFIG
    layer_positions = layer_positions or GENERIC_ENERGY_SANKEY_LAYER_POSITIONS

    nodes_set: set[str] = set()
    for edge in final_links.keys():
        src, dst = edge.split(":")
        nodes_set.add(src)
        nodes_set.add(dst)

    node_labels = sorted(nodes_set)

    node_colors: list[str] = []
    node_x: list[float] = []
    node_y: list[float] = []
    for node in node_labels:
        layer, y, color = node_config.get(node, (1.5, 0.5, "gray"))
        node_colors.append(color)
        node_x.append(layer_positions.get(layer, 0.5))
        node_y.append(y)

    source_indices: list[int] = []
    target_indices: list[int] = []
    link_values: list[float] = []
    link_colors: list[str] = []
    for edge, (value, color) in final_links.items():
        src, dst = edge.split(":")
        source_indices.append(node_labels.index(src))
        target_indices.append(node_labels.index(dst))
        link_values.append(value)
        link_colors.append(color)

    return {
        "node_labels": node_labels,
        "node_colors": node_colors,
        "node_x": node_x,
        "node_y": node_y,
        "source_indices": source_indices,
        "target_indices": target_indices,
        "link_values": link_values,
        "link_colors": link_colors,
    }


def _stage1_resolve_paths(
    *,
    project_root: Optional[Path | str],
    des_csv_path: Optional[Path | str],
    pv_output_dir: Optional[Path | str],
    input_csv_path: Optional[Path | str],
    params_json_path: Optional[Path | str],
) -> Dict[str, Path]:
    root = Path(project_root).resolve() if project_root is not None else _infer_project_root()

    des_csv = Path(des_csv_path).resolve() if des_csv_path is not None else (root / "data" / "outputs" / "DES_data.csv")
    pv_dir = Path(pv_output_dir).resolve() if pv_output_dir is not None else (root / "data" / "outputs" / "pv")
    input_csv = (
        Path(input_csv_path).resolve()
        if input_csv_path is not None
        else (root / "data" / "inputs" / "Input_kfw55_2_el.csv")
    )
    params_json = (
        Path(params_json_path).resolve()
        if params_json_path is not None
        else (root / "data" / "inputs" / "input_params.json")
    )

    if not des_csv.exists():
        raise FileNotFoundError(f"DES output CSV not found: {des_csv}")
    if not pv_dir.exists():
        raise FileNotFoundError(f"PV output directory not found: {pv_dir}")
    if not input_csv.exists():
        raise FileNotFoundError(f"Input demand CSV not found: {input_csv}")
    if not params_json.exists():
        raise FileNotFoundError(f"Params JSON not found: {params_json}")

    return {"root": root, "des_csv": des_csv, "pv_dir": pv_dir, "input_csv": input_csv, "params_json": params_json}


def _stage2_load_inputs(paths: Dict[str, Path]) -> Dict[str, Any]:
    df = pd.read_csv(paths["des_csv"], sep=",", index_col=DES_DATE_INDEX_COL)
    df.index = pd.to_datetime(df.index)

    latest_pv_file = _find_latest_csv(paths["pv_dir"])
    pv_df = pd.read_csv(latest_pv_file)
    pv_df.index = pd.to_datetime(pv_df[PV_INDEX_COL])
    pv_df.index = pv_df.index.tz_localize(None)

    input_df = pd.read_csv(paths["input_csv"], sep=",", skiprows=[0])
    input_df.index = pd.to_datetime(input_df[INPUT_TIME_COL])

    with open(paths["params_json"], "r", encoding="utf-8") as f:
        params: Dict[str, Any] = json.load(f)

    params_hp = params.get("hp")
    params_ctrl = params.get("ctrl")
    params_hwt = params.get("tank")

    if params_ctrl is not None and "tank" in params:
        params_ctrl["tank"] = params["tank"]

    init_vals_tanks = params.get("init_vals_tank")
    params_chp = params.get("params_chp")
    params_boiler = params.get("params_boiler")

    return {
        "df_raw": df,
        "latest_pv_file": latest_pv_file,
        "pv_df": pv_df,
        "input_df": input_df,
        "params": params,
        "params_hp": params_hp,
        "params_ctrl": params_ctrl,
        "params_hwt": params_hwt,
        "params_chp": params_chp,
        "params_boiler": params_boiler,
        "init_vals_tanks": init_vals_tanks,
    }


def _stage3_prepare_frames(loaded: Dict[str, Any]) -> Dict[str, Any]:
    df = _merge_pv_and_dedup(loaded["df_raw"], loaded["pv_df"])
    df, untranslated_columns = _apply_column_translation(df)
    df = df.apply(pd.to_numeric, errors="coerce")
    df_monthly = df.resample("ME").sum() / 4
    return {"df": df, "df_monthly": df_monthly, "untranslated_columns": untranslated_columns}


def _stage4_compute_outputs(*, df: pd.DataFrame, input_df: pd.DataFrame, params: Dict[str, Any], step_size: Optional[float]) -> Dict[str, Any]:
    resolved_step_size = _resolve_step_size(step_size)
    energies, init_energy, end_energy = _compute_energies(df, params=params, step_size=resolved_step_size)
    elec_links_df, elec_links = _build_electrical_links(df, input_df=input_df, step_size=resolved_step_size)
    thermal_links = _build_thermal_links(energies=energies, init_energy=init_energy, end_energy=end_energy)
    final_links = {**elec_links, **thermal_links}
    return {
        "resolved_step_size": resolved_step_size,
        "energies": energies,
        "init_energy": init_energy,
        "end_energy": end_energy,
        "elec_links_df": elec_links_df,
        "elec_links": elec_links,
        "thermal_links": thermal_links,
        "final_links": final_links,
    }


if __name__ == "__main__":
    out = prepare_visu_v2(verbose=True)
    print(
        "prepare_visu_v2 OK | ",
        "df:",
        out["df"].shape,
        "| final_links:",
        len(out["final_links"]),
        "| latest_pv:",
        out["latest_pv_file"],
    )
