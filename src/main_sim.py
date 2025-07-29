import mosaik
import mosaik.util
from mosaik_components.pv.configurations import generate_configurations, Scenarios
import os
import sys
import nest_asyncio
nest_asyncio.apply()

import logging
# from utils.setup_logging import setup_logging

import cProfile
import pstats

from multiprocessing import Process

import json
from datetime import datetime
import hashlib

#setup the logger
# setup_logging()
logger = logging.getLogger("mosaik_logger")

current_dir = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(current_dir, "..", 'data/outputs')
sys.path.append(os.path.join(current_dir, ".."))

from src.models import controller_mosaik
from src.models import chp_mosaik
from src.models import gasboiler_mosaik
from src.models import pvlib_model
#______________________________moved outside method, to be accessible from other scripts(visu.ipynb)
#TODO use the param file in visu
STEP_SIZE = 60*15 # step size 15 minutes
HV = 10833.3 #Heating value of natural gas in Wh/m^3; standard cubic meter

ref_param_filename = 'ref_params.json'
param_export_filename = 'used_params.json' # TODO pass this in des_sim parameter list
def export2json(params_dict):
    filename = os.path.join(OUTPUT_PATH, 'used_params.json')
    with open(filename, 'w') as f:
        json.dump(params_dict, f, indent = 4)

def generatePrefix(current_params, ref_param_name) :
    changes_dict = {}  #this dict will store the keys and their changes, could be exported with a unique key.
    filename = os.path.join(OUTPUT_PATH, ref_param_name)
    prefix = ''
    if not os.path.exists(filename):
        prefix += '_'
        return prefix, changes_dict
 
    with open(filename, 'r') as f:
        old_params = json.load(f)

    for comp, prms in current_params.items():
        for key, val in prms.items():
            if old_params[comp][key] != val:
                if type(val) == float or type(val) == int:               
                    diff = val - old_params[comp][key] if old_params[comp][key] is not None else val
                    prefix += f"{comp}.{key}+{diff}_"
                    changes_dict[f'{comp}.{key}'] = diff

                else :
                    prefix += str(key) + '~' + str(val)+ '_'
                    changes_dict[f'{comp}.{key}'] = f'{old_params[comp][key]}~{val}'
    return prefix, hash_encrypt(changes_dict)

def hash_encrypt(changes):

    change_str = json.dumps(changes, sort_keys=True)
    hash_str = hashlib.sha256(change_str.encode()).hexdigest()[:8]

    # Optionally store the mapping for future lookup
    # with open(os.path.join(OUTPUT_PATH, f'{hash_str}_changes.json'), 'w') as f:
        # json.dump(changes, f, indent=4)
    return hash_str

def run_DES(params):
    sim_config = {
        'EnergyTransformer' : {
            'python' : 'models.EnergyTransformer_frame:TransformerSimulator',
        },
        'Boilersim_v2' : {
            'python' : 'models.boiler_model_v2:TransformerSimulator'
        },
        'Chpsim_v2' : {
            'python' : 'models.chp_model_v2:TransformerSimulator'
        },
        
        'CSV': {
            'python': 'mosaik_csv:CSV',
        },
        'CSV_writer': {
            'python': 'mosaik_csv_writer:CSVWriter'
        },
        'HeatPumpSim': {
            'python': 'mosaik_components.heatpump.Heat_Pump_mosaik:HeatPumpSimulator',
        },
        'HotWaterTankSim': {
            'python': 'mosaik_components.heatpump.hotwatertank.hotwatertank_mosaik:HotWaterTankSimulator',
        
        },
        
        'ControllerSim': {
            'python': 'models.controller_mosaik:ControllerSimulator',
            
        },
        'CHPSim': {
            'python': 'models.chp_mosaik:CHPSimulator',
        },
        
        'PVSim': {
                'python': 'mosaik_components.pv.pvsimulator:PVSimulator',
        },
        'Boilersim' : {
                'python' : 'models.gasboiler_mosaik:Boilersimulator',
        },

        # 'PVsim_pvlib' : {
        #         'python' : 'mosaik_components.pv.photovoltaic_simulator:PVSimulator'
        # },
        # 'MeteoSim': {
        #         # 'python': 'mosaik_csv:CSV'
        # }


    }
    
    # Create World
    world = mosaik.World(sim_config)
    START = '2022-01-01 00:00:00'
    END =  365*24*60*60 # one year in seconds

    # unpacking input params
    params_boiler = params['boiler']
    params_hp = params['hp']
    params_chp = params['chp']
    params_ctrl = params['ctrl']
    params_hwt = params['tank']
    init_vals_hwt0 = params['init_vals_tank']['init_vals_hwt0']
    init_vals_hwt1 = params['init_vals_tank']['init_vals_hwt1']
    init_vals_hwt2 = params['init_vals_tank']['init_vals_hwt2']    
    params_chp = params['params_chp']
    params_boiler = params['params_boiler']
    params_chp['step_size'] = STEP_SIZE   


    # -----------------------------------------pv-------------------------------------------------------------------------------------
    #Standalone pvmodel-------------------------------------------------
    pvlib_model.sim()
    pv_results = os.path.abspath(os.path.join(os.path.dirname( __file__ ),'PVlib_output.csv')) 
    pv_csv = world.start('CSV', sim_start = START, datafile = pv_results)

    pv_mod = pv_csv.Data.create(1)
        
    #---------pvsimulator.py-----------------------------------------------------
    
    # parameters for pv model
    # LAT = 32.0
    # AREA = 100
    # EFF = 0.5
    # EL = 32.0
    # AZ = 0.0

    # DNI_DATA = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'data','inputs', 'solar_data_HSO.csv')) # pv
    # pv_sim = world.start("PVSim",start_date=START,step_size=STEP_SIZE) # pv
    # DNI_sim = world.start("CSV", sim_start=START, datafile=DNI_DATA) # pv
    
    # pv_model = pv_sim.PV.create(1, latitude=LAT, area=AREA,efficiency=EFF, el_tilt=EL, az_tilt=AZ) # pv
    # DNI_model = DNI_sim.DNI.create(1) # pv
    
    
    #-------------PVlib(mosaik adapter )---------------------------------------------
    # pv_count = 1
    # pv_config = {str(i) : generate_configurations(Scenarios.BUILDING) for i in range(pv_count)}

    # METEO_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data','inputs', 'Braunschweig_meteodata_2022_15min.csv') # pvlib
    # pv_sim_pvlib = world.start("PVsim_pvlib", start_date=START, step_size=STEP_SIZE, pv_data=pv_config,) # pvlib (takes 4:01 minutes for 1 year)
    # meteo_sim = world.start("CSV", sim_start=START, datafile=METEO_DATA) # pvlib (takes 13:16 minutes for 1 year)
    
    # pv_model_pvlib = pv_sim_pvlib.PVSim.create(pv_count) # PVlib
    # meteo_model = meteo_sim.Braunschweig.create(1) # pvlib

    #------------------------------------------PV END-----------------------------------------------------------------------------------------------------------------  

    # ----------------------Input data csv------------------------
    HEAT_LOAD_DATA = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'data', 'inputs', 'Input_kfw55_2_el.csv'))
    # configure the simulator
    csv = world.start('CSV', sim_start=START, datafile=HEAT_LOAD_DATA)
    # Instantiate model
    heat_load = csv.HEATLOAD.create(1)

    # ------------------Output data storage-----------------------
    prefix, hash_prefix = generatePrefix(params, ref_param_filename)
    # hash_prefix = ''
    
    # configure the simulator
    csv_sim_writer = world.start('CSV_writer', start_date= START, date_format='%Y-%m-%d %H:%M:%S',
                                output_file=OUTPUT_PATH+f'/{hash_prefix}try_DES_data.csv')

    csv_debug_writer = world.start('CSV_writer', start_date='2022-01-01 00:00:00', date_format='%Y-%m-%d %H:%M:%S',
                                output_file='utils/debug.csv')
    # Instantiate model
    csv_writer = csv_sim_writer.CSVWriter(buff_size=15 * 60 * 60)
    csv_debug = csv_debug_writer.CSVWriter(buff_size=15 * 60 * 60)
    #-------------------------------------------------------------

    # configure other simulators
    heatpumpsim = world.start('HeatPumpSim', step_size=STEP_SIZE)
    hwtsim0 = world.start('HotWaterTankSim', step_size=STEP_SIZE, config=params_hwt)
    hwtsim1 = world.start('HotWaterTankSim', step_size=STEP_SIZE, config=params_hwt)
    hwtsim2 = world.start('HotWaterTankSim', step_size=STEP_SIZE, config=params_hwt)
    ctrlsim = world.start('ControllerSim', step_size=STEP_SIZE)
    chpsim = world.start('Chpsim_v2', step_size = STEP_SIZE, params = params_chp)
    boilersim = world.start('Boilersim_v2', step_size = STEP_SIZE, params = params_boiler)
    
    # Instantiate other models
    heatpump = heatpumpsim.HeatPump.create(1, params=params_hp)
    chp = chpsim.Transformer.create(1, params=params_chp)
    hwts0 = hwtsim0.HotWaterTank.create(1, params=params_hwt, init_vals=init_vals_hwt0)
    hwts1 = hwtsim1.HotWaterTank.create(1, params=params_hwt, init_vals=init_vals_hwt1)
    hwts2 = hwtsim2.HotWaterTank.create(1, params=params_hwt, init_vals=init_vals_hwt2)
    ctrls = ctrlsim.Controller.create(1, params=params_ctrl)
    boiler = boilersim.Transformer.create(1, params = params_boiler)

    # -------------------------------------------------------------Connect entities----------------------------------------------------------------------------

    world.connect(heat_load[0], ctrls[0], 'T_amb', ('Heat Demand [kW]', 'heat_demand'), ('Domestic hot water (kW)' ,  'dhw_demand'), ('Space heating (kW)', 'sh_demand')
                  , ('Timestamp', 'timestamp'), ('offset_Electricy demand[kW]', 'pred_el_demand'))
    world.connect(pv_mod[0], ctrls[0], ('Power[w]', 'pv_gen'))

    world.connect(ctrls[0], csv_debug, 'tes0_heat_out_F', 'tes0_heat_in_F', 'tes0_hp_out_F',
                'hp_in_F', 'tes1_hp_out_F'
                )
    
    """__________________________________________ hwts ___________________________________________________________________""" 

    world.connect(hwts0[0], ctrls[0], ('heat_out.T', 'tes0_heat_out_T'), 
                ('hp_out.T', 'hp_out_T'), ('sensor_00.T', 'bottom_layer_Tank0'), ('heat_out2.T','tes0_heat_out2_T'), ('sensor_01.T', 'middle_layer_Tank0'),
                ('heat_out2.F', 'tes0_heat_out2_F'), ('sensor_02.T', 'top_layer_Tank0'),
                time_shifted=True, initial_data={'heat_out.T':0, 'hp_out.T':0, 'sensor_00.T':0, 'heat_out2.T' : 0, 'heat_out2.F':0}
                )

    world.connect(ctrls[0], hwts0[0], ('tes0_heat_out_F', 'heat_out.F'),
                ('tes0_heat_out_T', 'heat_out.T'),
                ('tes0_heat_in_F', 'heat_in.F'),
                ('tes0_heat_in_T', 'heat_in.T'),('tes0_heat_out2_F', 'heat_out2.F'),('hwt0_hr_1', 'hr_1.P_th_set')
                )

    world.connect(hwts1[0], ctrls[0], 
                ('heat_out.T', 'tes1_heat_out_T'),
                ('T_mean', 'T_mean_hwt'), ('mass', 'hwt_mass'),
                ('sensor_02.T', 'top_layer_Tank1'),
                ('hp_out.T', 'tes1_hp_out_T'), ('heat_out2.T','tes1_heat_out2_T'),
                ('heat_out2.F', 'tes1_heat_out2_F'), ('sensor_01.T', 'middle_layer_Tank1'),
                time_shifted=True, initial_data={
                    'heat_out.T':0, 'heat_out2.T':0,'T_mean':0, 'mass':0, 
                    'sensor_02.T':0, 'hp_out.T':0}
                )

    world.connect(ctrls[0], hwts1[0], ('tes1_hp_out_F', 'hp_out.F'),
                ('tes1_heat_out_T', 'heat_out.T'), ('tes1_heat_out_F', 'heat_out.F'), ('tes1_heat_out2_F', 'heat_out2.F'),
                ('tes1_hp_out_T','hp_out.T'), ('hwt1_hr_1', 'hr_1.P_th_set')
                )

    world.connect(ctrls[0], hwts2[0], ('tes2_hp_out_T', 'hp_out.T'),
                ('tes2_hp_out_F', 'hp_out.F'),
                ('tes2_heat_out_F', 'heat_out.F'),('tes2_heat_out2_F', 'heat_out2.F'),
                ('T_amb', 'T_env'), ('hwt2_hr_1', 'hr_1.P_th_set'),
                time_shifted=True,
                initial_data={'tes2_heat_out_F': 0, 'T_amb': 0, 'tes2_hp_out_T':0, 'tes2_hp_out_F':0, 'tes2_heat_out2_F':0, 'hwt2_hr_1':0
                                },)

    world.connect(hwts2[0], ctrls[0], ('heat_out.T', 'tes2_heat_out_T'), ('chp_out.T', 'chp_out_T'),
                ('heat_out.F', 'tes2_heat_out_F'), ('sensor_00.T', 'bottom_layer_Tank2'), ('sensor_02.T', 'top_layer_Tank2'), ('heat_out2.T','tes2_heat_out2_T'),
                ('heat_out2.F', 'tes2_heat_out2_F'), ('sensor_01.T', 'middle_layer_Tank2'))
 

    """__________________________________________Boiler_______________________________________________________________________"""

    world.connect(hwts2[0], boiler[0], ('sensor_00.T', 'temp_in'))
    world.connect(boiler[0], hwts2[0], ('temp_out', 'boiler_in.T'), ('mdot','boiler_in.F'), ('mdot_neg', 'boiler_out.F'),
                    time_shifted=True, initial_data={'temp_out': 20, 'mdot':0, 'mdot_neg':0})
    
    world.connect(boiler[0], ctrls[0], ('P_th', 'boiler_supply'), ('uptime','boiler_uptime'),
                ('mdot', 'boiler_mdot'))
    
    world.connect(ctrls[0], boiler[0], ('boiler_demand', 'Q_demand'), ('boiler_status', 'status'),
                time_shifted=True,
                initial_data={'boiler_demand': 0})


    """__________________________________________CHP__________________________________"""  
    
    world.connect(hwts2[0], chp[0], ('sensor_00.T', 'temp_in'))
    world.connect(chp[0], hwts2[0], ('temp_out', 'chp_in.T'), ('mdot','chp_in.F'), ('mdot_neg', 'chp_out.F'),
                    time_shifted=True, initial_data={'temp_out': 20, 'mdot':0, 'mdot_neg':0})

    world.connect(chp[0], ctrls[0], ('P_th', 'chp_supply'), ('uptime', 'chp_uptime'), ('P_el', 'chp_el'),
                ('mdot', 'chp_mdot')) 

    world.connect(ctrls[0], chp[0], ('chp_demand', 'Q_demand'), ('chp_status' , 'status'),
                time_shifted=True,
                initial_data={'chp_demand': 90000}
                )

    """__________________________________________ heat pump ___________________________________________________________________""" 

    world.connect(heatpump[0], ctrls[0], ('Q_Supplied', 'hp_supply'), ('on_fraction', 'hp_on_fraction'), ('P_Required', 'HP_P_Required'),
                ('cond_m', 'hp_cond_m'))

    world.connect(ctrls[0], heatpump[0], ('hp_demand', 'Q_Demand'),
                'T_amb', 'heat_source_T', time_shifted=True,
                initial_data={'hp_demand': 0, 'T_amb': 5, 'heat_source_T': 5})

    world.connect(hwts0[0], heatpump[0], ('hp_out.T', 'cond_in_T'),
                time_shifted=True, initial_data={'hp_out.T':0}
                )

    world.connect(heatpump[0], hwts0[0], ('cond_m_neg', 'hp_out.F'),
                )

    world.connect(heatpump[0], hwts1[0], ('cons_T', 'hp_in.T'), ('cond_m', 'hp_in.F'),
                )


    """__________________________________________ PVsim ___________________________________________________________________""" 
    #? delete connections?
    # world.connect(      DNI_model[0],
    #                     pv_model[0],
    #                     ("DNI", "DNI[W/m2]"),
    #                 )
    # world.connect(
    #                     pv_model[0],
    #                     csv_writer,
    #                     "P[MW]", 
    #                 )

    # world.connect(
    #                     DNI_model[0],
    #                     csv_writer,
    #                     "DNI", 
    #                 )

    """__________________________________________ PVlib ___________________________________________________________________""" 

    # world.connect(
    #                     meteo_model[0],
    #                     pv_model_pvlib[0],
    #                     ("GlobalRadiation", "GHI[W/m2]"),
    #                     ("AirPressHourly", "Air[Pa]"),
    #                     ("AirTemperature", "Air[C]"),
    #                     ("WindSpeed", "Wind[m/s]"),
    #                 )

    # world.connect(
    #                     pv_model_pvlib[0],
    #                     csv_writer,
    #                     "P[MW]", # could change it to watts, make it easier in visu, to switch and compare!
    #                 )

    """__________________________________________ CSV ___________________________________________________________________""" 
    # connect everything to the csv writer
    world.connect(heat_load[0], csv_writer, 'T_amb', 'Heat Demand [kW]')
    world.connect(heatpump[0], csv_writer, 'Q_Demand', 'Q_Supplied', 'T_amb', 'heat_source_T', 'cons_T',
                'P_Required',
                'COP', 'cond_m', 'cond_in_T', 'on_fraction','Q_evap')

    world.connect(ctrls[0], csv_writer, 'heat_demand', 'heat_supply', 'hp_demand', 'hp_supply',
                'chp_demand', 'chp_supply', 'sh_supply', 'dhw_supply',
                'heat_in_F', 'heat_in_T', 'heat_out_F', 'heat_out_T', 
                'chp_in_F', 'chp_in_T', 'chp_out_F', 'chp_out_T', 'pv_gen',
                'hp_out_F', 'hp_out_T', 'P_hr', 'dt', 'boiler_demand', 'chp_uptime')

    world.connect(hwts0[0], csv_writer, 'sensor_00.T', 'sensor_01.T', 'sensor_02.T', 
                'heat_out.T', 'heat_out.F', 'hp_in.T', 'hp_in.F', 'hp_out.T',
                'hp_out.F', 'heat_in.T', 'heat_in.F','heat_out2.F', 'heat_out2.T',
                'T_mean')

    world.connect(hwts1[0], csv_writer, 'sensor_00.T', 'sensor_01.T', 'sensor_02.T', 
                'heat_out.T', 'heat_out.F', 'hp_in.T', 'hp_in.F', 'hp_out.T',
                'hp_out.F', 'heat_in.T', 'heat_in.F', 'heat_out2.F', 'heat_out2.T',
                'T_mean')

    world.connect(hwts2[0], csv_writer, 'sensor_00.T', 'sensor_01.T', 'sensor_02.T', 
                'heat_out.T', 'heat_out.F', 'hp_in.T', 'hp_in.F', 'hp_out.T',
                'hp_out.F', 'heat_in.T', 'heat_in.F',
                'T_mean', 'hr_1.P_th', 'heat_out2.F', 'heat_out2.T')

    # world.connect(chp[0], csv_writer, 'eff_el', 'nom_P_th', 'mdot', 'mdot_neg', 'temp_in', 'Q_Demand', 'temp_out',
    #                'P_th', 'P_el', 'fuel_m3', 'chp_uptime'
    #               )  
    world.connect(chp[0], csv_writer,  'P_th', 'mdot', 'mdot_neg', 'temp_in', 'Q_demand', 'temp_out',
                    'P_el', 'uptime'
                  )  
    # world.connect(boiler[0], csv_writer, 'P_th', 'Q_Demand', 'temp_out', 'fuel_m3', 'mdot')   
    world.connect(boiler[0], csv_writer, 'P_th', 'Q_demand', 'temp_out', 'mdot')   


    """__________________________________________ world run _______________________________________________________________________________________________________________"""

    
    # To start heatpump as first simulator
    world.set_initial_event(heatpump[0].sid)
    
    # Run simulation
    world.run(until=END)

    #logger message
    logger.info(f"Scenario successfully simulated : {hash_prefix}.") #It is possible to have different logger levels depending on how important the information of the logger is.
    # Levels are (debug, info, warning, error)
    print(f'\n output : {hash_prefix, prefix}')
    export2json(params) #Exporting current parameters to a json, to be available to compare in next iteration.
    
    #warning log
    # logger.warning("Result of the simulation is:" +str(result))

    # plot the data flow
    mosaik.util.plot_dataflow_graph(world, folder=os.path.join(current_dir, 'utils/util_figures'), show_plot=False)

def pvsim():
    pvlib_model.sim()

if __name__ == "__main__":  
   
    # unpacking parameters from teh input json
    filename = 'input_params.json'
    path = os.path.join('..', 'data', 'inputs', filename)
    with open(path, 'r') as f:
        params = json.load(f)
    
    run_DES(params) #this will be executed only when this file is run directly.
    
    # pvsim()
# cProfile.run('run_DES()', 'profile_output') 
# p = pstats.Stats('profile_output')

