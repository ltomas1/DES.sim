import mosaik
import mosaik.util
from mosaik_components.pv.configurations import generate_configurations, Scenarios
import os
import sys
import nest_asyncio
nest_asyncio.apply()

import logging
from utils.setup_logging import setup_logging
#setup the logger
setup_logging()
logger = logging.getLogger("mosaik_logger")

current_dir = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(current_dir, "..", 'data/outputs')
sys.path.append(os.path.join(current_dir, ".."))

from models import controller_mosaik
from models import chp_mosaik
from models import gasboiler_mosaik
#______________________________moved outside method, to be accessible from other scripts(visu.ipynb)
 

HV = 10833.3 #Heating value of natural gas in Wh/m^3; standard cubic meter

# Heat pump
params_hp = {'hp_model': 'Air_60kW',
                'heat_source': 'Air',
                'calc_mode': 'fast'
                }

# CHP
params_chp = {'eff_el': 0.54,
            'nom_P_th': 92_000,
            'mdot': 4.0,
            'startup_coeff' : [-2.63, 3.9, 0.57], #coefficients to model the startup behaviour, in the order : Intercept, x,x^2,x^3...
            'eta' : 0.5897, # fuel efficiency of chp, from datasheet.
            'hv' : HV
            }

#Gas boiler
params_boiler = {'eta' : 0.98, 'hv' : HV,
                    'nom_P_th' : [0, 74000, 148000, 222000, 296000, 370000], #Operating points of boiler, in W
                    'Set_Temp' : 75
                    }

# hot water tank
params_hwt = {
        'height': 2500,
        'volume': 5000,
        'T_env': 20.0,
        'htc_walls': 0.28,
        'htc_layers': 0.897,
        'n_layers': 3,
        'n_sensors': 3,
        'connections': {
            'heat_in': {'pos': 150},
            'heat_out': {'pos': 2350},
            'chp_in': {'pos': 2300},
            'chp_out': {'pos': 50},
            'hp_in': {'pos': 2200},
            'hp_out': {'pos': 100},
            'boiler_in' : {'pos' : 2400},
            'boiler_out' : {'pos' : 120}
        },
    }

init_vals_hwt0 = {
        'layers': {'T': [40.0, 30.0, 20.0]}
    }

init_vals_hwt1 = {
        'layers': {'T': [40.0, 30.0, 20.0]}
    }

init_vals_hwt2 = {
        'layers': {'T': [80.0, 70.0, 60.0]}
    }


# Parameters for controller model
params_ctrl = {
    'T_hp_sp_h': 65,
    'T_chp_h' : 75,
    'T_hp_sp_l': 35,
    'T_hr_sp': 65,
    'heat_rT' : 35,
    'operation_mode': 'heating',
    'control_strategy': '5',
    'hr_mode' : 'off'
}

def run_DES():
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
            'python': 'models.controller_mosaik:ControllerSimulator',
            
        },
        'CHPSim': {
            'python': 'models.chp_mosaik:CHPSimulator',
        },
        
        'PVSim': {
                'python': 'mosaik_components.pv.pvsimulator:PVSimulator'
        },
        'Boilersim' : {
                'python' : 'models.gasboiler_mosaik:Boilersimulator'
        }

    }


    # Create World
    world = mosaik.World(sim_config)

    START = '2022-01-01 00:00:00'
    # END =  365*24*60*60 # one year in seconds
    STEP_SIZE = 60*15 # step size 15 minutes 
    END =  30*24*60*60 # one year in seconds.
    

    # parameters for pv model
    LAT = 32.0
    AREA = 100
    EFF = 0.5
    EL = 32.0
    AZ = 0.0
    DNI_DATA = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'data','inputs', 'solar_data_HSO.csv')) # pv
    # METEO_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'Braunschweig_meteodata_2022_15min.csv') # pvlib

    pv_count = 1
    pv_config = {str(i) : generate_configurations(Scenarios.BUILDING) for i in range(pv_count)}
    tank_count = 2

    # configure the simulator
    heatpumpsim = world.start('HeatPumpSim', step_size=STEP_SIZE)
    hwtsim0 = world.start('HotWaterTankSim', step_size=STEP_SIZE, config=params_hwt)
    hwtsim1 = world.start('HotWaterTankSim', step_size=STEP_SIZE, config=params_hwt)
    hwtsim2 = world.start('HotWaterTankSim', step_size=STEP_SIZE, config=params_hwt)
    ctrlsim = world.start('ControllerSim', step_size=STEP_SIZE)
    chpsim = world.start('CHPSim', step_size=STEP_SIZE)

    boilersim = world.start('Boilersim', step_size = STEP_SIZE)


    # pv_sim = world.start("PVSim", start_date=START, step_size=STEP_SIZE, pv_data=pv_config,) # pvlib (takes 4:01 minutes for 1 year)
    pv_sim = world.start("PVSim",start_date=START,step_size=STEP_SIZE) # pv
    DNI_sim = world.start("CSV", sim_start=START, datafile=DNI_DATA) # pv
    # meteo_sim = world.start("CSV", sim_start=START, datafile=METEO_DATA) # pvlib (takes 13:16 minutes for 1 year)

    # Input data csv
    HEAT_LOAD_DATA = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', 'data', 'inputs', 'Input_profile3.csv'))
    # configure the simulator
    csv = world.start('CSV', sim_start=START, datafile=HEAT_LOAD_DATA)
    # Instantiate model

    # Output data storage
    # configure the simulator
    csv_sim_writer = world.start('CSV_writer', start_date='2022-01-01 00:00:00', date_format='%Y-%m-%d %H:%M:%S',
                                output_file=OUTPUT_PATH+'/DES_data.csv')

    csv_debug_writer = world.start('CSV_writer', start_date='2022-01-01 00:00:00', date_format='%Y-%m-%d %H:%M:%S',
                                output_file='utils/debug.csv')

    # Instantiate model
    heatpump = heatpumpsim.HeatPump.create(1, params=params_hp)
    chp = chpsim.CHP.create(1, params=params_chp)
    hwts0 = hwtsim0.HotWaterTank.create(1, params=params_hwt, init_vals=init_vals_hwt0)
    hwts1 = hwtsim1.HotWaterTank.create(1, params=params_hwt, init_vals=init_vals_hwt1)
    hwts2 = hwtsim2.HotWaterTank.create(1, params=params_hwt, init_vals=init_vals_hwt2)
    ctrls = ctrlsim.Controller.create(1, params=params_ctrl)
    heat_load = csv.HEATLOAD.create(1)

    boiler = boilersim.GasBoiler.create(1, params = params_boiler)



    # pv_model = pv_sim.PVSim.create(pv_count) # PVlib
    pv_model = pv_sim.PV.create(1, latitude=LAT, area=AREA,efficiency=EFF, el_tilt=EL, az_tilt=AZ) # pv
    DNI_model = DNI_sim.DNI.create(1) # pv
    # meteo_model = meteo_sim.Braunschweig.create(1) # pvlib

    # Instantiate model
    csv_writer = csv_sim_writer.CSVWriter(buff_size=15 * 60 * 60)
    csv_debug = csv_debug_writer.CSVWriter(buff_size=15 * 60 * 60)

    # Connect entities

    world.connect(heat_load[0], ctrls[0], 'T_amb', ('Heat Demand [kW]', 'heat_demand'))
    world.connect(ctrls[0], csv_debug, 'tes0_heat_out_F', 'tes0_heat_in_F', 'tes0_hp_out_F',
                'hp_in_F', 'tes1_hp_out_F'
                )
    
    """__________________________________________ hwts ___________________________________________________________________""" 

    world.connect(hwts0[0], ctrls[0], ('heat_out.T', 'tes0_heat_out_T'), 
                ('hp_out.T', 'hp_out_T'), ('sensor_00.T', 'bottom_layer_Tank0'),
                time_shifted=True, initial_data={'heat_out.T':0, 'hp_out.T':0, 'sensor_00.T':0}
                )

    world.connect(ctrls[0], hwts0[0], ('tes0_heat_out_F', 'heat_out.F'),
                ('tes0_heat_out_T', 'heat_out.T'),
                ('heat_in_F', 'heat_in.F'),
                ('heat_in_T', 'heat_in.T'),
                )

    world.connect(hwts1[0], ctrls[0], 
                ('heat_out.T', 'tes1_heat_out_T'),
                ('T_mean', 'T_mean_hwt'), ('mass', 'hwt_mass'),
                ('sensor_02.T', 'top_layer_Tank1'),
                ('hp_out.T', 'tes1_hp_out_T'),
                time_shifted=True, initial_data={
                    'heat_out.T':0, 'T_mean':0, 'mass':0, 
                    'sensor_02.T':0, 'hp_out.T':0}
                )

    world.connect(ctrls[0], hwts1[0], ('tes1_hp_out_F', 'hp_out.F'),
                ('tes1_heat_out_T', 'heat_out.T'), ('tes1_heat_out_F', 'heat_out.F'),
                ('tes1_hp_out_T','hp_out.T')
                )

    world.connect(ctrls[0], hwts2[0], ('tes2_hp_out_T', 'hp_out.T'),
                ('tes2_hp_out_F', 'hp_out.F'),
                ('heat_out_F', 'heat_out.F'), 
                ('T_amb', 'T_env'),
                time_shifted=True,
                initial_data={'heat_out_F': 0, 'T_amb': 0, 'tes2_hp_out_T':0, 'tes2_hp_out_F':0
                                },)

    world.connect(hwts2[0], ctrls[0], ('heat_out.T', 'heat_out_T'), ('chp_out.T', 'chp_out_T'),
                ('heat_out.F', 'heat_out_F'), ('sensor_00.T', 'bottom_layer_Tank2'), ('sensor_02.T', 'top_layer_Tank2'))
 
 
    """__________________________________________Boiler_______________________________________________________________________"""

    world.connect(hwts2[0], boiler[0], ('sensor_00.T', 'temp_in'))
    world.connect(boiler[0], hwts2[0], ('temp_out', 'boiler_in.T'), ('mdot','boiler_in.F'), ('mdot_neg', 'boiler_out.F'),
                    time_shifted=True, initial_data={'temp_out': 20, 'mdot':0, 'mdot_neg':0})
    
    world.connect(boiler[0], ctrls[0], ('P_th', 'boiler_supply'), ('boiler_uptime','boiler_uptime'),
                ('mdot', 'boiler_mdot'))
    
    world.connect(ctrls[0], boiler[0], ('boiler_demand', 'Q_Demand'), 'boiler_status',
                time_shifted=True,
                initial_data={'boiler_demand': 0})
    
    
    """__________________________________________ CHP ________________________________________________________________________"""

    world.connect(hwts2[0], chp[0], ('sensor_00.T', 'temp_in'))
    world.connect(chp[0], hwts2[0], ('temp_out', 'chp_in.T'), ('mdot','chp_in.F'), ('mdot_neg', 'chp_out.F'),
                    time_shifted=True, initial_data={'temp_out': 20, 'mdot':0, 'mdot_neg':0})

    world.connect(chp[0], ctrls[0], ('P_th', 'chp_supply'), ('chp_uptime', 'chp_uptime'),
                ('mdot', 'chp_mdot')) 

    world.connect(ctrls[0], chp[0], ('chp_demand', 'Q_Demand'), ('chp_status' , 'chp_status'),
                time_shifted=True,
                initial_data={'chp_demand': 90000}
                )

    """__________________________________________ heat pump ___________________________________________________________________""" 

    world.connect(heatpump[0], ctrls[0], ('Q_Supplied', 'hp_supply'), ('on_fraction', 'hp_on_fraction'),
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


    """__________________________________________ PV ___________________________________________________________________""" 

    world.connect(      DNI_model[0],
                        pv_model[0],
                        ("DNI", "DNI[W/m2]"),
                    )
    world.connect(
                        pv_model[0],
                        csv_writer,
                        "P[MW]", 
                    )

    world.connect(
                        DNI_model[0],
                        csv_writer,
                        "DNI", 
                    )

    """__________________________________________ PVlib ___________________________________________________________________""" 

    # world.connect(
    #                     meteo_model[0],
    #                     pv_model[0],
    #                     ("GlobalRadiation", "GHI[W/m2]"),
    #                     ("AirPressHourly", "Air[Pa]"),
    #                     ("AirTemperature", "Air[C]"),
    #                     ("WindSpeed", "Wind[m/s]"),
    #                 )

    # world.connect(
    #                     pv_model[0],
    #                     csv_writer,
    #                     "P[MW]",
    #                 )

    """__________________________________________ CSV ___________________________________________________________________""" 
    # connect everything to the csv writer
    world.connect(heat_load[0], csv_writer, 'T_amb', 'Heat Demand [kW]')
    world.connect(heatpump[0], csv_writer, 'Q_Demand', 'Q_Supplied', 'T_amb', 'heat_source_T', 'cons_T',
                'P_Required',
                'COP', 'cond_m', 'cond_in_T', 'on_fraction','Q_evap')

    world.connect(ctrls[0], csv_writer, 'heat_demand', 'heat_supply', 'hp_demand', 'hp_supply',
                'chp_demand', 'chp_supply',
                'heat_in_F', 'heat_in_T', 'heat_out_F', 'heat_out_T', 
                'chp_in_F', 'chp_in_T', 'chp_out_F', 'chp_out_T',
                'hp_out_F', 'hp_out_T', 'P_hr', 'dt', 'boiler_demand', 'chp_uptime')

    world.connect(hwts0[0], csv_writer, 'sensor_00.T', 'sensor_01.T', 'sensor_02.T', 
                'heat_out.T', 'heat_out.F', 'hp_in.T', 'hp_in.F', 'hp_out.T',
                'hp_out.F', 'heat_in.T', 'heat_in.F',
                'T_mean')

    world.connect(hwts1[0], csv_writer, 'sensor_00.T', 'sensor_01.T', 'sensor_02.T', 
                'heat_out.T', 'heat_out.F', 'hp_in.T', 'hp_in.F', 'hp_out.T',
                'hp_out.F', 'heat_in.T', 'heat_in.F',
                'T_mean')

    world.connect(hwts2[0], csv_writer, 'sensor_00.T', 'sensor_01.T', 'sensor_02.T', 
                'heat_out.T', 'heat_out.F', 'hp_in.T', 'hp_in.F', 'hp_out.T',
                'hp_out.F', 'heat_in.T', 'heat_in.F',
                'T_mean')

    world.connect(chp[0], csv_writer, 'eff_el', 'nom_P_th', 'mdot', 'mdot_neg', 'temp_in', 'Q_Demand', 'temp_out',
                   'P_th', 'P_el', 'fuel_m3', 'chp_uptime'
                  )   
    world.connect(boiler[0], csv_writer, 'P_th', 'Q_Demand', 'temp_out', 'fuel_m3', 'mdot')   


    """__________________________________________ world run ______________________________________________________________"""

    # # Set execution order so the controller receives up-to-date values
    # world.set_execution_order([heat_load, hwts0, hwts1, hwts2, ctrls, chp, heatpump, boiler])

    # # Ensure initial data transfer before first step
    # world.step(0)
    
    
    # To start heatpump as first simulator
    world.set_initial_event(heatpump[0].sid)
    
    # Run simulation
    world.run(until=END)

    #logger message
    logger.info("Scenario successfully simulated.") #It is possible to have different logger levels depending on how important the information of the logger is.
    # Levels are (debug, info, warning, error)
    
    #warning log
    # logger.warning("Result of the simulation is:" +str(result))

    # plot the data flow
    mosaik.util.plot_dataflow_graph(world, folder='utils/util_figures', show_plot=False)

if __name__ == "__main__":  
    run_DES() 
    
