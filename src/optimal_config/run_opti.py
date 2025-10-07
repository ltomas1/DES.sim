from pathlib import Path
import sys
import os

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))  # so 'src' is importable
os.chdir(os.path.join(os.path.dirname(__file__), '../..'))

import pandas as pd
import json
import pickle
from post_processing import postprocessing
from src.main_sim import run_DES
import itertools
import copy
import logging
import traceback
from tqdm import tqdm
import concurrent.futures
import numpy as np


df_combinations = pd.read_csv(os.path.join(os.path.dirname(__file__), '../../data/inputs/sample_plan_300.csv'))

current_dir = os.getcwd()
input_params_path = os.path.join(current_dir, 'data/inputs/input_params.json')
scenario_path = os.path.join(current_dir,'data/inputs/scenario.pkl')

with open(input_params_path, 'r') as file:
    input_params = json.load(file)
with open(scenario_path, "rb") as f:
    scenario = pickle.load(f)

# ------------------------------------------------------------------------------------------------------------------------------------------------------------
logfile = Path("data/logs/run_opti.log")

# clear old logs once
logfile.write_text("")

logging.basicConfig(
    filename=logfile,
    filemode="a", 
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.info("Starting simulation...")

# delete old pvlib output files (containing PVlib_output in the name)
output_dir = os.path.join(os.path.dirname(__file__), '../../data/outputs/pv')
for filename in os.listdir(output_dir):
    if "PVlib_output" in filename:
        os.remove(os.path.join(output_dir, filename))

def run_instance(args):
    config_params, des_config_i = args
    try:
        print(f"[Worker] Starting simulation for {des_config_i}", flush=True)
        sim_data = run_DES(config_params)
        cost, co2, aux_heat = postprocessing(sim_data, config_params, scenario)
        print(f"[Worker] Finished simulation for {des_config_i}", flush=True)
        logging.info(f"Simulation finished successfully: {des_config_i}")
        return {**des_config_i, "costs": cost, "co2": co2, "aux_heater": aux_heat}
    except Exception as e:
        print(f"[Worker] ERROR for {des_config_i}: {e}", flush=True)
        traceback.print_exc()
        logging.exception(f"Simulation for {des_config_i} crashed: {e}")
        return {**des_config_i, "costs": np.nan, "co2": np.nan, "aux_heater": np.nan}

def main():
    # load scenario once
    with open(scenario_path, "rb") as f:
        global scenario
        scenario = pickle.load(f)

    results = []
    batch_size = os.cpu_count()

    batch_params = []
    for _, des_config_i in df_combinations.iterrows():
        config_params = copy.deepcopy(input_params)
        config_params['hp']['hp_model'] = des_config_i['hp']
        config_params['params_chp']['heat_out'] = [0, des_config_i['chp']]
        config_params['params_boiler']['heat_out'] = [0, des_config_i['boiler']]
        config_params['ctrl']['supply_config'] = des_config_i['supply_config']
        config_params['tank']['heating_rods']['hr_1']['mode'] = des_config_i['hr_mode']
        config_params['ctrl']['T_dhw_sp'] = des_config_i['T_dhw_sp']
        config_params['tank']['volume'] = des_config_i['hwt_volume']
        config_params['pv']['nom_power'] = des_config_i['pv']

        batch_params.append((config_params, des_config_i.to_dict()))

    with concurrent.futures.ProcessPoolExecutor(max_workers=batch_size) as executor:
        futures = [executor.submit(run_instance, args) for args in batch_params]
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            try:
                results.append(future.result())
            except Exception as e:
                logging.error(f"Future failed: {e}")

    # delete pvlib output files again
    for filename in os.listdir(output_dir):
        if "PVlib_output" in filename:
            os.remove(os.path.join(output_dir, filename))

    data = pd.DataFrame(results)

    data.to_csv(os.path.join(os.path.dirname(__file__), '../../data/outputs/optimal_config_results.csv'), index=True)

if __name__ == "__main__":
    main()
