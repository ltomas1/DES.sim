import os
import json
import subprocess
import sys
import multiprocessing

cwd = os.path.dirname(os.path.abspath(__file__))

path_main = os.path.join(cwd, '..', 'src')
sys.path.append(path_main)
sys.path.insert(0,path_main)
from main_sim import run_DES

input_path = os.path.join(cwd, '..', 'data', 'inputs', 'input_params.json')

with open(input_path,'r') as f:
    params = json.load(f)

params1 = params
params1['ctrl']['T_hp_sp_winter'] += 3

params2 = params
params2['ctrl']['heat_rT'] = 25

params_list = [params1, params2]

def run_instance(params):
    run_DES(params)

if __name__ == "__main__":
    # Optional: Limit number of cores to use
    num_cores = multiprocessing.cpu_count()  # or set manually

    with multiprocessing.Pool(processes=num_cores) as pool:
        pool.map(run_instance, params_list)

        #multiprocessing still not ready!!