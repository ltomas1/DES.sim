import os
import json
import subprocess
import sys
import multiprocessing
import multiprocessing.dummy as mpd
import matplotlib
matplotlib.use('Agg')
import copy

cwd = os.path.dirname(os.path.abspath(__file__))

path_main = os.path.join(cwd, '..', 'src')
sys.path.append(path_main)
sys.path.insert(0,path_main)
from main_sim import run_DES

input_path = os.path.join(cwd, '..', 'data', 'inputs', 'input_params.json')

with open(input_path,'r') as f:
    params = json.load(f)

params1 = copy.deepcopy(params)
params1['ctrl']['T_dhw_sp'] = 65

params2 = copy.deepcopy(params)
params2['ctrl']['T_dhw_sp'] = 60

params3 = copy.deepcopy(params)
params3['ctrl']['T_dhw_sp'] = 55



params_list = [params1, params2, params3]

def run_instance(params):
    run_DES(params)

if __name__ == "__main__":
    # Optional: Limit number of cores to use
    num_cores = multiprocessing.cpu_count()  # or set manually

    with multiprocessing.Pool(processes=3) as pool:
        pool.map(run_instance, params_list)

        #multiprocessing still not ready!!