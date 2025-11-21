import mosaik
import mosaik.util
from mosaik_components.pv.configurations import generate_configurations, Scenarios
import os
import sys
import nest_asyncio
nest_asyncio.apply()

import logging
# from utils.setup_logging import setup_logging

from multiprocessing import Process

import json
import hashlib

import time

#setup the logger
# setup_logging()
logger = logging.getLogger("mosaik_logger")

current_dir = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(current_dir, "..", 'data/outputs')
sys.path.append(os.path.join(current_dir, ".."))

from src.models import controller_mosaik
from src.models import pvlib_model

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

def run_DES(params, step_sz):
    perf_start = time.perf_counter()
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
        '3wayvalve' : {
            'python' : 'models.3wayvalve:SimInterface'
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
    # START = '2024-01-01 00:00:00'
    START = '2024-01-01 00:00:00'
    END =  365*24*60*60 # one year in seconds

    params['ctrl']['tank'] = params['tank'] 
    init_vals_hwt0 = params['init_vals_tank']['init_vals_hwt0']
    init_vals_hwt1 = params['init_vals_tank']['init_vals_hwt1']
    init_vals_hwt2 = params['init_vals_tank']['init_vals_hwt2']    

    params['params_chp']['step_size'] = step_sz

    params['ctrl']['Ideal_hr_mode'] = 'off' #aux heater to identify supply deficits.

    hp_tank2share = 1 # how much of the heat pump output goes to tank 2

    params_hp3wv = {'eid_prefix': 'HP_3wv'
                    }
    debug = 'off'
    params['ctrl']['debug'] = debug
    params['hp']['debug'] = debug
    params['tank']['debug'] = debug

    # -----------------------------------------pv-------------------------------------------------------------------------------------
    #Standalone pvmodel-------------------------------------------------
    # pvlib_model.sim(params_pv)
    # pv_results = os.path.abspath(os.path.join(os.path.dirname( __file__ ),'PVlib_output.csv')) 
    # pv_csv = world.start('CSV', sim_start = START, datafile = pv_results)

    # pv_mod = pv_csv.Data.create(1)
        
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
    HEAT_LOAD_DATA = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'data', 'inputs', 'demand_ES04.csv'))

    # configure the simulator
    csv = world.start('CSV', sim_start=START, datafile=HEAT_LOAD_DATA)
    # Instantiate model
    heat_load = csv.Data.create(1) 


    # ------------------Output data storage-----------------------
    # prefix, hash_prefix = generatePrefix(params, ref_param_filename)
    prefix, hash_prefix = '',''
    
    # configure the simulator
    csv_sim_writer = world.start('CSV_writer', start_date= START, date_format='%Y-%m-%d %H:%M:%S',
                                output_file=OUTPUT_PATH+f'/{hash_prefix}Durlach_sim.csv')

    # Instantiate model
    csv_writer = csv_sim_writer.CSVWriter(buff_size=15 * 60 * 60)
    #-------------------------------------------------------------
    # finer_step_sz = 300  # 5 minutes for heat pump and hot water tank
    # configure other simulators
    heatpumpsim = world.start('HeatPumpSim', step_size=step_sz)
    hwtsim0 = world.start('HotWaterTankSim', step_size=step_sz, config={**params['tank'], "Tanknumber" : 0})
    hwtsim1 = world.start('HotWaterTankSim', step_size=step_sz,config={**params['tank'], "Tanknumber" : 1})
    hwtsim2 = world.start('HotWaterTankSim', step_size=step_sz, config={**params['tank'], "Tanknumber" : 2})
    ctrlsim = world.start('ControllerSim', step_size=step_sz, params = params['ctrl'])
    boilersim = world.start('Boilersim_v2', step_size = step_sz, params = params['params_boiler'])
    hp_3wayvalvesim = world.start('3wayvalve', step_size = step_sz, params = params_hp3wv)
    
    # Instantiate other models
    heatpump = heatpumpsim.HeatPump.create(1, params=params['hp'])
    # chp = chpsim.Transformer.create(1, params=params['params_chp'])
    hwts0 = hwtsim0.HotWaterTank.create(1, params=params['tank'], init_vals=init_vals_hwt0)
    hwts1 = hwtsim1.HotWaterTank.create(1, params=params['tank'], init_vals=init_vals_hwt1)
    hwts2 = hwtsim2.HotWaterTank.create(1, params=params['tank'], init_vals=init_vals_hwt2)
    ctrls = ctrlsim.Controller.create(1, params=params['ctrl'])
    boiler = boilersim.Transformer.create(1, params = params['params_boiler'])
    hp_3wayvalve = hp_3wayvalvesim.Valve.create(1, params = params_hp3wv)

    # -------------------------------------------------------------Connect entities----------------------------------------------------------------------------

    world.connect(heat_load[0], ctrls[0], 'T_amb',('heat_source_T', 'heat_source_T'), ('Heat Demand [kW]', 'heat_demand'), ('Domestic hot water (kW)' ,  'dhw_demand'), ('Space heating (kW)', 'sh_demand')
                  , ('Timestamp', 'timestamp'))
    
    """__________________________________________ hwts ___________________________________________________________________""" 

    world.connect(hwts0[0], ctrls[0], ('heat_out.T', 'tank_connections.tank0.heat_out_T'), 
              ('hp_out.T', 'hp_out_T'),('sensor_00.T', 'tank_temps.tank0.sensor_0'), ('heat_out2.T','tank_connections.tank0.heat_out2_T'), 
              ('sensor_01.T', 'tank_temps.tank0.sensor_1'),('heat_out2.F', 'tank_connections.tank0.heat_out2_F'), 
              ('sensor_02.T', 'tank_temps.tank0.sensor_2'),time_shifted=True, 
              initial_data={'heat_out.T':0, 'hp_out.T':0, 'sensor_00.T':0, 
                            'heat_out2.T' : 0, 'heat_out2.F':0})

    world.connect(ctrls[0], hwts0[0], 
              ('tank_connections.tank0.heat_out_F', 'heat_out.F'),
              ('tank_connections.tank0.heat_out_T', 'heat_out.T'),
              ('tank_connections.tank0.heat_in_F', 'heat_in.F'),
              ('tank_connections.tank0.heat_in_T', 'heat_in.T'),
              ('tank_connections.tank0.heat_out2_F', 'heat_out2.F'),
              ('hwt0_hr_1', 'hr_1.P_th_set'))

    world.connect(hwts1[0], ctrls[0], 
              ('heat_out.T', 'tank_connections.tank1.heat_out_T'),('T_mean', 'T_mean_hwt'), 
              ('mass', 'hwt_mass'),('sensor_02.T', 'tank_temps.tank1.sensor_2'),
              ('hp_out.T', 'tank_connections.tank1.hp_out_T'),('heat_out2.T','tank_connections.tank1.heat_out2_T'),
              ('heat_out2.F', 'tank_connections.tank1.heat_out2_F'),('sensor_01.T', 'tank_temps.tank1.sensor_1'),
              time_shifted=True, 
              initial_data={'heat_out.T':0, 'heat_out2.T':0,'T_mean':0, 'mass':0, 
                            'sensor_02.T':0, 'hp_out.T':0})

    world.connect(ctrls[0], hwts1[0], 
              ('tank_connections.tank1.hp_out_F', 'hp_out.F'),('tank_connections.tank1.heat_out_T', 'heat_out.T'), 
              ('tank_connections.tank1.heat_out_F', 'heat_out.F'),('tank_connections.tank1.heat_out2_F', 'heat_out2.F'),
              ('tank_connections.tank1.hp_out_T','hp_out.T'), ('hwt1_hr_1', 'hr_1.P_th_set'),
              ('tank_connections.tank1.heat_in_F', 'heat_in.F'),
              ('tank_connections.tank1.heat_in_T', 'heat_in.T'), ('tank_connections.tank1.boiler_out_F', 'boiler_out.F'),('tank_connections.tank1.boiler_out_T', 'boiler_out.T'))

    world.connect(ctrls[0], hwts2[0], 
              ('tank_connections.tank2.hp_out_T', 'hp_out.T'),('tank_connections.tank2.hp_out_F', 'hp_out.F'),
              ('tank_connections.tank2.heat_out_F', 'heat_out.F'),('tank_connections.tank2.heat_out2_F', 'heat_out2.F'),
              ('T_amb', 'T_env'), ('hwt2_hr_1', 'hr_1.P_th_set'),
              ('tank_connections.tank2.heat_in_F', 'heat_in.F'),
              ('tank_connections.tank2.heat_in_T', 'heat_in.T'),
              )

    
    world.connect(hwts2[0], ctrls[0], ('heat_out.T', 'tank_connections.tank2.heat_out_T'), 
              ('heat_out.F', 'tank_connections.tank2.heat_out_F'), 
              ('sensor_00.T', 'tank_temps.tank2.sensor_0'),('sensor_02.T', 'tank_temps.tank2.sensor_2'), 
              ('heat_out2.T','tank_connections.tank2.heat_out2_T'),('heat_out2.F', 'tank_connections.tank2.heat_out2_F'), 
              ('sensor_01.T', 'tank_temps.tank2.sensor_1'),
              time_shifted=True,
              initial_data = {'heat_out.T':0, 'heat_out.F':0, 'sensor_00.T':0, 'sensor_01.T':0, 'sensor_02.T':0,
                              'heat_out2.T':0, 'heat_out2.F':0, 'sensor_01.T':0})
 

    """__________________________________________Boiler_______________________________________________________________________"""
    
    world.connect(hwts2[0], boiler[0], ('sensor_00.T', 'temp_in'),
                  time_shifted=True,
                initial_data={'sensor_00.T':20}
                )
    world.connect(boiler[0], hwts2[0], ('temp_out', 'boiler_in.T'), ('mdot','boiler_in.F'), ('mdot_neg', 'boiler_out.F'),
                    )
    
    world.connect(boiler[0], ctrls[0], ('P_th', 'generators.boiler_supply'), ('uptime','boiler_uptime'),
                )
    
    world.connect(ctrls[0], boiler[0], ('generators.boiler_demand', 'Q_demand'), ('generators.boiler_status', 'status'),
                time_shifted=True,
                initial_data={'generators.boiler_demand': 0})



    """__________________________________________ 3 way valve ___________________________________________________________________""" 

    world.connect(ctrls[0], hp_3wayvalve[0], ('HP3wv_out1_share', 'out1_share'),
                    time_shifted = True,
                    initial_data = {'HP3wv_out1_share' : 1}
                )
    """__________________________________________ heat pump ___________________________________________________________________""" 

    world.connect(heatpump[0], ctrls[0], ('Q_Supplied', 'generators.hp_supply'), ('on_fraction', 'hp_on_fraction'), ('P_Required', 'HP_P_Required'),
                ('cond_m', 'hp_cond_m'))

    # heat_source_T has to be provided for fast mode, T_amb is not
    world.connect(ctrls[0], heatpump[0], ('generators.hp_demand', 'Q_Demand'),
                'T_amb', 'heat_source_T', time_shifted=True,
                initial_data={'generators.hp_demand': 0, 'T_amb': 5, 'heat_source_T': 5})

    world.connect(hwts0[0], heatpump[0], ('hp_out.T', 'cond_in_T'),
                time_shifted=True, initial_data={'hp_out.T':0}
                )

    #splitting flow between the two tanks.
    world.connect(heatpump[0], hp_3wayvalve[0], ('cond_m', 'flows.in'), ('cons_T', 'flows.temp'))

    # #Heat pump flow to tank 1
    world.connect(hp_3wayvalve[0], hwts1[0], ('flows.out_1', 'hp_in.F'), ('flows.temp', 'hp_in.T'))
    world.connect(hp_3wayvalve[0], ctrls[0], ('flows.out_1', 'tank_connections.tank1.hp_in_F'), ('flows.temp', 'tank_connections.tank1.hp_in_T'))

    # # Heat pump flow to tank 2
    world.connect(hp_3wayvalve[0], hwts2[0], ('flows.out_2', 'hp_in.F'), ('flows.temp', 'hp_in.T'))
    world.connect(hp_3wayvalve[0], ctrls[0], ('flows.out_2', 'tank_connections.tank2.hp_in_F'), ('flows.temp', 'tank_connections.tank2.hp_in_T'))
    


    world.connect(heatpump[0], hwts0[0], ('cond_m_neg', 'hp_out.F'),)
    world.connect(heatpump[0], ctrls[0], ('cond_m_neg', 'tank_connections.tank0.hp_out_F'))

              


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
    world.connect(heat_load[0], csv_writer, 'T_amb', 'Heat Demand [kW]', 'Domestic hot water (kW)', 'Space heating (kW)')
    world.connect(heatpump[0], csv_writer, 'Q_Demand', 'Q_Supplied', 'T_amb', 'heat_source_T', 'cons_T',
                'P_Required',
                'COP', 'cond_m', 'cond_in_T', 'on_fraction','Q_evap')

    world.connect(ctrls[0], csv_writer, 'heat_demand', 'heat_supply', 'generators.hp_demand', 'generators.hp_supply',
                 'sh_supply', 'dhw_supply', 
                 'pv_gen',
                 'IdealHrodsum', 'generators.boiler_demand',  'req_shTsup')

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
    world.connect(boiler[0], csv_writer, 'P_th', 'Q_demand', 'temp_out', 'mdot')   

    world.connect(hp_3wayvalve[0], csv_writer, 'flows.in', 'flows.out_1', 'flows.out_2', 'flows.temp')

    mosaik.util.connect_many_to_one(world, [hwts0[0], hwts1[0], hwts2[0]], csv_writer, 'heat_in.F',
    'heat_out.F','chp_in.F','chp_out.F','hp_in.F','hp_out.F',
    'boiler_in.F','boiler_out.F','heat_out2.F','heat_in2.F'  )


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

    

    elapsed = time.perf_counter() - perf_start
    print(f'elapsed:{elapsed}')
    
    # plot the data flow
    # mosaik.util.plot_dataflow_graph(world, folder=os.path.join(current_dir, 'utils/util_figures'), show_plot=False)

    return elapsed

def pvsim():
    pvlib_model.sim()

def rename_cols(df):
    columns = {}
    for col in df.columns:
        attr = col.rsplit('-', 1)[1] if '-' in col else col
        entity = col.split('-', 1)[0].replace('Sim', '') if '-' in col else ''
        
        # entity = 
        new_col = f"{entity}_{attr}" 
        columns[col] = new_col
    return columns

# def dirty_analysis():
    
STEP_SIZE = 60*5 # step size 15 minutes
if __name__ == "__main__":  
   
    # unpacking parameters from teh input json
    filename = 'input_params_valid.json'
    path = os.path.join('..', 'data', 'inputs', filename)
    with open(path, 'r') as f:
        params = json.load(f)
    
    run_DES(params, STEP_SIZE) #this will be executed only when this file is run directly.
    
    # pvsim()


