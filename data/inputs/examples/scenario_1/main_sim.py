import mosaik
import mosaik.util
import os
import sys
import nest_asyncio
nest_asyncio.apply()
import logging
import json
from pathlib import Path

#setup the logger
logger = logging.getLogger("mosaik_logger")

PROJECT_ROOT = Path(__file__).resolve().parent # Goes up to the main repo folder
OUTPUT_PATH = PROJECT_ROOT / "data" / "outputs"

from des_sim.models import des_pv
STEP_SIZE = 60*15 # step size 15 minutes
HV = 10833.3 #Heating value of natural gas in Wh/m^3; standard cubic meter

def export2json(params_dict):
    filename = OUTPUT_PATH / 'used_params.json'
    with open(filename, 'w') as f:
        json.dump(params_dict, f, indent = 4)

def run_DES(params, collect=True, plot_graph=False):
    sim_config = {
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
            'python': 'des_sim.models.controller_mosaik:ControllerSimulator',
            
        },
        'Collector': {
                'python': 'des_sim.models.collector:Collector',
        }
    }
    
    # Create World
    
    world = mosaik.World(sim_config, mosaik_config={'addr':('127.0.0.1', 0)})
    START = '2022-01-01 00:00:00'
    END =  365*24*60*60 # one year in seconds

    # unpacking input params
    params_hp = params['hp']
    params_hwt = params['tank']
    params['ctrl']['tank'] = params['tank']
    init_vals_hwt0 = params['init_vals_tank']['init_vals_hwt0']
        
    # ----------------------Input data csv------------------------
    HEAT_LOAD_DATA = PROJECT_ROOT / "data" / "inputs" / "Input_kfw55_2_el.csv"    # configure the simulator
    csv = world.start('CSV', sim_start=START, datafile=HEAT_LOAD_DATA)
    # Instantiate model
    heat_load = csv.HEATLOAD.create(1)

    # ------------------Output data storage-----------------------
    # configure the simulator
    csv_sim_writer = world.start('CSV_writer', start_date= START, date_format='%Y-%m-%d %H:%M:%S',
                                output_file=OUTPUT_PATH / 'DES_data.csv')
    # Instantiate model
    collector = world.start('Collector')
    csv_writer = csv_sim_writer.CSVWriter(buff_size=15 * 60 * 60)
    col = collector.Collector()

    #-------------------------------------------------------------
    # configure other simulators
    heatpumpsim = world.start('HeatPumpSim', step_size=STEP_SIZE)
    hwtsim0 = world.start('HotWaterTankSim', step_size=STEP_SIZE, config={**params_hwt, "Tanknumber" : 0})
    ctrlsim = world.start('ControllerSim', step_size=STEP_SIZE, params = params['ctrl'])
    
    
    # Instantiate other models
    heatpump = heatpumpsim.HeatPump.create(1, params=params_hp)
    hwts0 = hwtsim0.HotWaterTank.create(1, params=params_hwt, init_vals=init_vals_hwt0)
    ctrls = ctrlsim.Controller.create(1, params=params['ctrl'])
    # -------------------------------------------------------------Connect entities----------------------------------------------------------------------------

    world.connect(heat_load[0], ctrls[0], 'T_amb', ('Heat Demand [kW]', 'heat_demand'), ('Domestic hot water (kW)' ,  'dhw_demand'), ('Space heating (kW)', 'sh_demand')
                  , ('Timestamp', 'timestamp'), ('offset_Electricy demand[kW]', 'pred_el_demand'))

    """__________________________________________ hwts ___________________________________________________________________""" 

    world.connect(hwts0[0], ctrls[0], ('heat_out.T', 'tank_connections.tank0.heat_out_T'), ("heat_out.F", "tank_connections.tank0.heat_out_F") , ('T_mean', 'T_mean_hwt'), ('mass', 'hwt_mass'), 
              ('hp_out.T', 'hp_out_T'),('sensor_00.T', 'tank_temps.tank0.sensor_0'), ('heat_out2.T','tank_connections.tank0.heat_out2_T'), 
              ('sensor_01.T', 'tank_temps.tank0.sensor_1'),('heat_out2.F', 'tank_connections.tank0.heat_out2_F'), 
              ('sensor_02.T', 'tank_temps.tank0.sensor_2'),time_shifted=True, 
              initial_data={'heat_out.T':0, 'hp_out.T':0, 'sensor_00.T':0, 'T_mean':0, 'mass':0,
                            'heat_out2.T' : 0, 'heat_out2.F':0})

    world.connect(ctrls[0], hwts0[0], 
              ('tank_connections.tank0.heat_in_F', 'heat_in.F'),
              ('tank_connections.tank0.heat_in_T', 'heat_in.T'),
              ('tank_connections.tank0.heat_out2_F', 'heat_out2.F'),
              ('tank_connections.tank0.hp_out_F', 'hp_out.F'),
              ('tank_connections.tank0.hp_out_T', 'hp_out.T'),
              ('hwt0_hr_1', 'hr_1.P_th_set'))
    
    """__________________________________________ heat pump ___________________________________________________________________""" 

    world.connect(heatpump[0], ctrls[0], ('Q_Supplied', 'generators.hp_supply'), ('on_fraction', 'hp_on_fraction'),
                ('cond_m', 'hp_cond_m'), ('P_Required','HP_P_Required'))

    world.connect(ctrls[0], heatpump[0], ('generators.hp_demand', 'Q_Demand'),
                'T_amb', 'heat_source_T', time_shifted=True,
                initial_data={'generators.hp_demand': 0, 'T_amb': 5, 'heat_source_T': 5})

    world.connect(hwts0[0], heatpump[0], ('hp_out.T', 'cond_in_T'),
                time_shifted=True, initial_data={'hp_out.T':0}
                )

    world.connect(heatpump[0], hwts0[0], ('cons_T', 'hp_in.T'), ('cond_m', 'hp_in.F'), ('cond_m_neg', 'hp_out.F'),
                )

    world.connect(heatpump[0], ctrls[0], ('cond_m_neg', 'tank_connections.tank0.hp_out_F'), ('cond_m', 'tank_connections.tank0.hp_in_F'),)


    """__________________________________________ CSV ___________________________________________________________________""" 
    # connect everything to the csv writer
    world.connect(heat_load[0], csv_writer, 'T_amb', 'Heat Demand [kW]', 'Domestic hot water (kW)', 'Space heating (kW)')
    world.connect(heatpump[0], csv_writer, 'Q_Demand', 'Q_Supplied', 'T_amb', 'heat_source_T', 'cons_T',
                'P_Required',
                'COP', 'cond_m', 'cond_in_T', 'on_fraction','Q_evap')

    world.connect(ctrls[0], csv_writer, 'heat_demand', 'heat_supply', 'generators.hp_demand', 'generators.hp_supply',
                 'sh_supply', 'dhw_supply', 
                 
                 'IdealHrodsum',  'req_shTsup', 'dch_power')

    world.connect(hwts0[0], csv_writer, 'sensor_00.T', 'sensor_01.T', 'sensor_02.T', 
                'heat_out.T', 'heat_out.F', 'hp_in.T', 'hp_in.F', 'hp_out.T',
                'hp_out.F', 'heat_in.T', 'heat_in.F','heat_out2.F', 'heat_out2.T',
                'T_mean')

    # auto-connect *all* source attributes to collector
    def connect_all_attrs(world, src_sim, src_entities, collector_ent):
        for e in src_entities:
            model = e.type
            attrs = src_sim.meta['models'][model]['attrs']  # list of attribute names
            if attrs:
                world.connect(e, collector_ent, *attrs)     # connect each attr by name
                
    connect_all_attrs(world, ctrlsim, ctrls, col)
    connect_all_attrs(world, heatpumpsim, heatpump, col)
    # connect_all_attrs(world, hwtsim0, hwts0, col)
    # connect_all_attrs(world, hwtsim1, hwts1, col)
    # connect_all_attrs(world, hwtsim2, hwts2, col)    
    connect_all_attrs(world, csv, heat_load, col)
    
    """__________________________________________ world run _______________________________________________________________________________________________________________"""

    
    # To start heatpump as first simulator
    world.set_initial_event(heatpump[0].sid)
    
    data = None
    if collect == True:
        data = collector.dump() 

    # Run simulation
    world.run(until=END)

    # plot the data flow
    if plot_graph == True:
        mosaik.util.plot_dataflow_graph(world, folder=f"{PROJECT_ROOT}/data/outputs", show_plot=False)

    return data
    
    #logger message
    # logger.info(f"Scenario successfully simulated : {hash_prefix}.") #It is possible to have different logger levels depending on how important the information of the logger is.
    # Levels are (debug, info, warning, error)
    # print(f'\n output : {hash_prefix, prefix}')
    # export2json(params) #Exporting current parameters to a json, to be available to compare in next iteration.
    
    #warning log
    # logger.warning("Result of the simulation is:" +str(result))

    

# def pvsim():
#     pvlib_model.sim()

if __name__ == "__main__":  
   
    # unpacking parameters from teh input json
    filename = 'input_params.json'
    path = PROJECT_ROOT / "data" / "inputs" / filename
    with open(path, 'r') as f:
        params = json.load(f)
    
    run_DES(params) #this will be executed only when this file is run directly.
    
    # pvsim()
# import cProfile
# import pstats
# cProfile.run('run_DES()', 'profile_output') 
# p = pstats.Stats('profile_output')
