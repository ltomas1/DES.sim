__doc__ = """
The controller module contains an updated class for the controller model (:class:`Controller`).
"""
#Logging setup------------------------------------------------------------------------------------------------------------#
import logging

logger_controller = logging.getLogger("mosaik_logger")
logger_controller.setLevel(logging.DEBUG)  # Log everything (DEBUG, INFO, WARNING, ERROR)

# Create a file handler to store logs
file_handler_controller = logging.FileHandler("controller_mosaik_simulation.log")  # Save to file
file_handler_controller.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

logger_controller.addHandler(file_handler_controller)
#----------------------------------------------------------------------------------------------------------------------------#
# %%
import pandas as pd
import numpy as np
from tqdm import tqdm
import os
import json
from collections import defaultdict
from src.utils import helpers

import operator
# %%
class Controller():
    """
        Simulation model of a controller.

        The controller model used in this work utilizes simple Boolean logic to:
            1.	Match the heating demands with the supply from the hot water tank/back up heaters
            2.	Control the operation of the heat pump using different control strategies

        Controller parameters are provided at instantiation by the dictionary **params**. This is an example, how
        the dictionary might look like::

            params = {
                'T_hp_sp_h': 50,
                'T_hp_sp_l': 40,
                'T_hr_sp_hwt': 40,
                'T_hr_sp': 35,
                'sh_dT': 7,
                'operation_mode': 'heating',
                'control_strategy': '1'
                }

        Explanation of the entries in the dictionary:

        * **T_hp_sp_h**: The higher temperature set point for heat pump operation (in °C)
        * **T_hp_sp_l**: The lower temperature set point for heat pump operation (in °C)
        * **T_hr_sp_hwt**: The temperature set point for the back up heater within the hot water tank (in °C)
        * **T_hr_sp**: The temperature set point for the back up heater (in °C)
        * **sh_dT**: The temperature difference of the water in the space heating supply circuit (in °C)
        * **operation_mode**: The operation mode of the heating system, either 'heating' or 'cooling'
        * **control_strategy**: The control strategy to be used for the heat pump operation. Currently, two
          strategies have been implemented ('1' & '2')

        """
        
    def __init__(self, params):
        # Temperature setpoints
        self.T_hp_sp_winter = params.get('T_hp_sp_winter')
        self.T_hp_sp_summer = params.get('T_hp_sp_summer')
        self.T_hp_sp_surplus = params.get('T_hp_sp_surplus')
        self.T_hr_sp_hwt = params.get('T_hr_sp_hwt', None)
        self.T_dhw_sp = params.get('T_dhw_sp', None)
        self.T_chp_h = params.get('T_chp_h')
        self.heat_rT = params.get('heat_rT', 20) #Specific to the 2-runner setup
        # Control mode
        self.operation_mode = params.get('operation_mode', 'heating')
        self.control_strategy = params.get('control_strategy', '1')
        self.idealheater = params.get('Ideal_hr_mode', 'off').lower()
        self.boiler_delay = params.get('boiler_delay')
        self.T_dhw_buffer = params.get('T_dhw_buffer', 5)

        #supply configuration
        self.config = params.get('supply_config')
        self.sh_out = params.get('sh_out')  #Tank which serves as the Output connection for space heating
        self.sh_out2 = params.get('sh_out2', None)
        self.dhw_out = params.get('dhw_out')##Tank which serves as the Output connection for hot water demand
        self.ret_tank = params.get('return_tank', self.sh_out) #Tank which serves as the return connection; used except for 4-runner!!!
        self.sh_ret = params.get('sh_ret', None) #Tank which serves as the return connection for space heating
        self.dhw_ret = params.get('dhw_ret', None)
        self.dhw_Tdelta = params.get('dhw_Tdelta', 15) #The temperature difference in the dhw circuit.

        self.stepsize = params.get('step_size')
        self.boiler_mode = params.get('boiler_mode','off').lower()
        self.params_hwt = params.get('tank')

        
        self.gens = params.get('gens')
        self.no_tanks = params.get('NumberofTanks') # the number of tanks in the system
        self.tank_setup = params.get('TankbalanceSetup')# the tank connections in the system

        
        # --------------------------------Initialising attributes----------------------------------------------
        
        self.generators = {
            f'{gen}_{suffix}' : init for gen in self.gens for suffix, init in zip(['status', 'demand', 'supply'], ['off', 0, 0])
        }
        self.tanks = [f"tank{i}" for i in range(0,self.no_tanks)]
        
        self.tank_connections = {}
        for tank in self.tanks:
            self.tank_connections[tank] = {
                f'{port}_{suffix}' : 0 for port in params['tank']['connections'].keys() for suffix in ['T', 'F']
            }

        self.sensors = [f'sensor_{i}' for i in range(0, params['tank']['n_sensors'])]
        self.tank_temps = {
            tank : {sensor : 0 for sensor in self.sensors} for tank in self.tanks
            }
        
        # other attrs---------------------
        self.req_shTsup = None # ONLY for debugging, to see the required supply temp for SH circuit.

        self.T_amb = None                   # The ambient air temperature (in °C)
        self.heat_source_T = None           # The temperature of source for the heat pump (in °C)
        self.T_room = None                  # The temperature of the room (used in cooling mode, in °C)

        self.heat_demand = None             # The total heat demand from SH & DHW (in W)
        self.dhw_demand = None
        self.sh_demand = None
        self.dhw_supply, self.sh_supply, self.heat_supply = None, None, None  # The heat supplied for DHW, SH and total (in W)


        self.heat_dT = None                   # The temeprature difference between heat_in_T and heat_out_T (in K)

        self.hp_in_F = None                 # The mass flow of water into the hot water tank from heat pump (in kg/s)
        self.hp_in_T = None                 # The temperature of water into the hot water tank from heat pump (in °C)
        self.hp_out_F = None                # The mass flow of water from the hot water tank into heat pump (in kg/s)
        self.hp_out_T = None                # The temperature of water from the hot water tank into heat pump (in °C)
        self.hp_cond_m = None               # The mass flow of water in the condenser of heat pump (in kg/s)
        self.hp_on_fraction = None          # The fraction of the time step for which the heat pump is on

        self.chp_uptime = None              #Time since startup of chp
        self.boiler_uptime = None       # The time for which the boiler has been operational (in Seconds)
        self.dt = 0 #Time for how long top layer of Tank 3 below threshold, i.e chp not able to keep up with demand.
        
        self.T_mean_hwt = 0              # The mean temperature of the hot water tank (in °C)
        self.hwt_mass = 0                # The total mass of water inside the hot water tank (kg)

        self.hwt_hr_P_th_set = None         # The heat demand for the in built heating rod of the hot water tank (in W)

        self.max_flow = 20            #The max flow rate permissible in one step.
        self.IdealHrodsum = 0           # The sum of P_hr and space heating idealheater
        self.P_hr_sh = 0                #Instantatus of Ideal heater only for space heating.
        self.tcvalve1 = TCValve(self.max_flow)
        self.hr = idealHeatRod()
        self.hwt2_hr_1 = 0 #Inbuilt heatingrods
        self.hwt1_hr_1 = 0
        self.hwt0_hr_1 = 0

        self.pv_gen = None
        self.chp_el = None  #The electricity generation from the chp
        self.HP_P_Required = None #The power requirement of the heat pump

        self.pred_el_demand = None #The predicted/future electricity demand.
        
        self.timestamp = None
        self.hp_surplus = False

        self.HP3wv_out1_share = 1 # The share of the flow from the mixing valve going to output 1(tank 1)

        #Collecting all the attributes in init, to make it available in attrs list.
        self.attr_list = list(vars(self).keys())
        flat_keys = []

        # Flatten dict attributes
        for attr in self.attr_list:
            value = getattr(self, attr)   # get the actual object
            if isinstance(value, dict):
                for key, val in value.items():
                    if isinstance(val, dict):  # nested dict case
                        for subkey in val.keys():
                            flat_keys.append(f"{attr}.{key}.{subkey}")
                    else:
                        flat_keys.append(f"{attr}.{key}")

        # extend self.attr_list with the flattened keys
        self.attr_list.extend(flat_keys)
        # tqdm.write(f'attr_list')


    def get_init_attrs(self):
        return self.attr_list
    
    def step(self, time):
        """Perform simulation step with step size step_size"""
        # tqdm.write(f'controller step run at time:{time}')
        
        # Convert the heat demand available in kW to W
        if self.heat_demand is None or self.heat_demand < 0:
            self.heat_demand = 0
        else:
            self.heat_demand *= 1000

        if self.sh_demand is None or self.sh_demand < 0:
            self.sh_demand = 0
        else:
            self.sh_demand *= 1000

        if self.dhw_demand is None or self.dhw_demand < 0:
            self.dhw_demand = 0
        else:
            self.dhw_demand *= 1000
        
        self.timestamp = pd.to_datetime(self.timestamp)
        
        if self.timestamp.month <= 8 and self.timestamp.month >= 6 :
            self.season = 'summer'
        elif self.timestamp.month: #just checking if timestamp exists and month is a valid value.
            self.season = 'winter'
        else:
            self.season = None

        if self.timestamp.hour <= 18 and self.timestamp.hour >= 8:
            self.isday = True
        elif self.timestamp.hour:
            self.isday = False
        else:
            self.isday = None



        # ---------------------HP charge tank, 3 way valve--------------------------------------
        if self.season == 'summer':
            self.HP3wv_out1_share = 0 # all to tank 2(dhw tank)
        else:
            self.HP3wv_out1_share = 1 # to tank tank1 (middle, SH)

        
        # ------------------HP surplus mode def-----------------------------------------
        
        # if surplus electricity generation:
        if self.pv_gen and self.chp_el and self.pred_el_demand:
            if (self.pv_gen + self.chp_el - self.pred_el_demand) > 1 : 
                self.hp_surplus = True
            else:
                self.hp_surplus = False
        #----------------------------------------------------------------------
        # Calculate the mass flows, temperatures and heat from back up heater for the SH circuit
        self.calc_heat_supply(self.config)

        # --------------------------------------------------Inbuilt heating rods P required------------------

        # self.tankLayer_volume = 3.14 * self.params_hwt['height'] * (self.params_hwt['diameter']/2e3)**2  #height is in mm, so H/10^3 * density 1000kg/m3; so density omitted here!
        self.tankLayer_mass = self.params_hwt['volume'] * 1 / self.params_hwt['n_layers'] #1L = 1Kg
        
        # if chaning hr position, change the temp value here as well!
        if self.params_hwt['heating_rods']['hr_1']['mode'] == 'on' and self.tank_temps['tank2']['sensor_2'] < self.params_hwt['heating_rods']['hr_1']['T_max']:
            self.hwt2_hr_1 = self.tankLayer_mass * 4184 * (self.params_hwt['heating_rods']['hr_1']['T_max'] - self.tank_temps['tank2']['sensor_2'])

        self.hwt1_hr_1, self.hwt0_hr_1 = 0,0 

        # ------------------------------------------Control strategies for the operation of heat pump in heating mode
        if self.operation_mode.lower() == 'heating':
            #Datasheet logic control
            if self.control_strategy == '1':
                                
                
                #-------------------Heat pump----------------
                if self.season == 'winter':

                    if self.tank_temps['tank1']['sensor_1'] < self.T_hp_sp_winter: #Turns on only when below threshold of 35 degrees.
                        
                        self.generators['hp_status'] = 'on'
                        
                    if self.generators['hp_status'] == 'on' and self.isday: # Hp runs until upper threshold achieved.
                        if self.tank_temps['tank0']['sensor_0'] < self.T_hp_sp_winter:
                            self.generators['hp_demand'] = self.hwt_mass * 4184 * (self.T_hp_sp_winter - self.tank_temps['tank0']['sensor_0']) / self.step_size
                        
                        elif self.hp_surplus and self.tank_temps['tank0']['sensor_0'] < self.T_hp_sp_surplus:
                            self.generators['hp_demand'] =  self.hwt_mass * 4184 * (self.T_hp_sp_surplus - self.tank_temps['tank0']['sensor_0']) / self.step_size
                        
                        else:
                            self.generators['hp_demand'] = 0
                            self.generators['hp_status'] = 'off'
                    elif self.isday == False:
                        if self.tank_temps['tank0']['sensor_2'] < self.T_hp_sp_winter:
                            self.generators['hp_demand'] = self.hwt_mass * 4184 * (self.T_hp_sp_winter - self.tank_temps['tank0']['sensor_0']) / self.step_size
                        
                        elif self.hp_surplus and self.tank_temps['tank0']['sensor_0'] < self.T_hp_sp_surplus:
                            self.generators['hp_demand'] =  self.hwt_mass * 4184 * (self.T_hp_sp_surplus - self.tank_temps['tank0']['sensor_0']) / self.step_size
                        
                        else:
                            self.generators['hp_demand'] = 0
                            self.generators['hp_status'] = 'off'      
                    
                    else:
                        self.generators['hp_demand'] = 0

                if self.season == 'summer':

                    if self.tank_temps['tank2']['sensor_1'] < self.T_hp_sp_summer: #Turns on only when below threshold of 35 degrees.
                        
                        self.generators['hp_status'] = 'on'
                        
                    if self.generators['hp_status'] == 'on' and self.isday: # Hp runs until upper threshold achieved.
                        if self.tank_temps['tank0']['sensor_0'] < self.T_hp_sp_summer:
                            self.generators['hp_demand'] = self.hwt_mass * 4184 * (self.T_hp_sp_summer - self.tank_temps['tank0']['sensor_0']) / self.step_size
                                                
                        else:
                            self.generators['hp_demand'] = 0
                            self.generators['hp_status'] = 'off'
                    
                    elif self.isday == False:
                        if self.tank_temps['tank1']['sensor_1'] < self.T_hp_sp_summer:
                            self.generators['hp_demand'] = self.hwt_mass * 4184 * (self.T_hp_sp_summer - self.tank_temps['tank1']['sensor_1']) / self.step_size
                        
                        else:
                            self.generators['hp_demand'] = 0
                            self.generators['hp_status'] = 'off'      
                    
                    else:
                        self.generators['hp_demand'] = 0
                
                if self.generators['hp_status'] == None:
                        self.generators['hp_status'] = 'off'
                    
                #--------------------CHP----------------
                if self.tank_temps['tank2']['sensor_2'] < self.T_dhw_sp + self.T_dhw_buffer: #i.e high heat demand
                    self.generators['chp_status'] = 'on'
                    
                
                if self.generators['chp_status'] == 'on': #runs until bottom layer of tank 2 reaches the threshold
                    if self.tank_temps['tank2']['sensor_0'] < self.T_chp_h:
                        self.generators['chp_demand'] = self.hwt_mass * 4184 * (self.T_dhw_sp - self.tank_temps['tank2']['sensor_0']) / self.step_size
                    elif self.chp_uptime >= 15: #15 minute minimum runtime
                        self.generators['chp_demand'] = 0
                        self.generators['chp_status'] = 'off'
                    else:
                        self.generators['chp_demand'] = self.hwt_mass * 4184 * (self.T_dhw_sp - self.tank_temps['tank2']['sensor_0']) / self.step_size

                    # logger_controller.debug(f'time : {time} \tsensor_0 layer : {self.sensor_0_layer_T_chp}, uptime : {self.chp_uptime}, status : {self.chp_status}')
                else:
                    
                    self.generators['chp_demand'] = 0

                
                #-----------------Boiler------------------
                #If the CHP is not able to keep up :
                # Data transfer only at end of step, so this ensures, dt incremented after one step of chp.
                if self.tank_temps['tank2']['sensor_2'] < self.T_dhw_sp and self.chp_uptime > 0: 
                    self.dt += self.step_size
                else :
                    self.dt = 0
                
                if self.dt > self.boiler_delay and self.tank_temps['tank2']['sensor_2'] < self.T_dhw_sp and self.boiler_mode == 'on':
                     self.generators['boiler_status'] = 'on'
                    
                
                if self.generators['boiler_status'] == 'on':
                    if self.tank_temps['tank2']['sensor_0'] < self.T_chp_h:
                        self.generators['boiler_demand'] = self.hwt_mass * 4184 * (self.T_dhw_sp - self.tank_temps['tank2']['sensor_0']) / (self.step_size * 2) # heat up the entire tank to T_hr_sp in 2 time steps
                        # self.boiler_demand =  self.heat_demand             
                    elif self.boiler_uptime >= 15: #The transformer class has uptime in minutes, unlike the gasboiler model
                        self.generators['boiler_demand'] = 0
                        self.generators['boiler_status'] = 'off'
                    else :
                        self.generators['boiler_demand'] =  self.heat_demand
                        # tqdm.write(f'boiler uptim : {self.boiler_uptime}; in the last condition')
                else:
                    
                    self.generators['boiler_demand'] = 0
                
                # logger_controller.debug(f'time : {time}\t Top layer temp : {self.top_layer_Tank2}, uptime : {self.chp_uptime}, chpstatus : {self.chp_status}, dt : {self.dt}, boiler : {self.boiler_status}, boiler uptime : {self.boiler_uptime}\n')
            if self.control_strategy == '2':

                # new nested logi dict
                '''
                logic = {
                    'comp' : {
                        'turn-on' : {
                            'tank' :
                            'layer' :
                            't_low' :
                            't_high' :} },
                        'turn-off' :{
                            default = turn-on + 5C}},
                        'add_conds' :{ #this would have higher priority, can override the turn on/off temps.
                            'turn_on' : {'attr' : [sign(default = '<='), thresh_val]},
                            'turn_off' : , 
                        }
                '''
                # Could move these as well, somewhere common, the logic dict could be defined in main_sim, but later
                operatormapping = {
                    '<': operator.lt,
                    '>': operator.gt,
                    '<=': operator.le,
                    '>=': operator.ge
                }
                logic = {
                    'boiler' : {
                        'turn_on' : {
                            'tank' : 'tank2',
                            'layer' : 'sensor_2',
                            'turn_on_temp' : 60
                        },
                        'turn_off' :{
                            'turn_off_temp' : 68
                        }
                    },
                    'hp' : {
                        'turn_on' : {
                            'tank' : 'tank1',
                            'layer' : 'sensor_1',
                            'turn_on_temp' : 50
                        },
                        # 'turn_off' :{ 
                        #     'tank' : 'tank1',
                        #     'layer' : 'sensor_1',
                        #     'turn_off_temp' : 60
                        # },
                        'add_conditions' : {
                            'turn_off' : {'T_amb' : ['<=', 0]}
                        }
                    }
                }


                # could move these methods to __init__, but would decrease readability, with very little to no performance impact.
                def turn_on():
                    self.generators[f'{gen}_status'] = 'on'
                    self.generators[f'{gen}_demand'] = self.hwt_mass * 4184 * (temp_sp_low - self.tank_temps[tank_id][tank_layer]) / self.step_size
                def turn_off():
                    self.generators[f'{gen}_status'] = 'off'
                    self.generators[f'{gen}_demand'] = 0

                def check_add_conditions(add_cond_dict, key):
                    if key not in add_cond_dict.keys():
                        return False
                    
                    if len(add_cond_dict[key].keys()) > 2:
                        print("More than 2 additional conditions not supported yet!!")
                    for cond_2, thresh in add_cond_dict[key].items():
                        if isinstance(thresh, list):
                            op_str, thresh_val = thresh
                        else:
                            op_str, thresh_val = '<=', thresh
                        
                        op_func = operatormapping.get(op_str)
                        if op_func is None:
                            raise ValueError(f"Invalid operator '{op_str}' in additional conditions")
                        if op_func(getattr(self, cond_2), thresh_val): # operator.le(self.T_amb, thresh_val):
                            return True
                    return False


                for gen_, cond in logic.items():
                    #gen_ will be the exact key in the dict, with the dhw, sh suffix and such.

                    turn_on_cfg = cond.get('turn_on')
                    tank_id = turn_on_cfg.get('tank')
                    tank_layer = turn_on_cfg.get('layer')
                    temp_sp_low = turn_on_cfg.get('turn_on_temp')

                    turn_off_tank_id = cond.get('turn_off', {}).get('tank', tank_id) # defaults to the same tank as turn-on condition
                    turn_off_tank_layer = cond.get('turn_off', {}).get('layer', tank_layer)
                    temp_sp_high = cond.get('turn_off', {}).get('turn_off_temp', temp_sp_low + 5)

                    add_conditions = cond.get('add_conditions', {})

                    gen = next((base for base in self.gens if gen_.startswith(base)), None)
                    #To find the generator name from the unique list. Finds the first match.
                    
                    if gen is None:
                        raise RuntimeError(f"Generator '{gen_}' not found in self.gens list")
                    
                    # Turn on logic
                    if self.tank_temps[tank_id][tank_layer] <= temp_sp_low:
                        turn_on()
                    elif check_add_conditions(add_conditions, 'turn_on'): # this can overwrite the previous temp setpoints
                        turn_on()
                                
                    # Turn off logic
                    if self.tank_temps[turn_off_tank_id][turn_off_tank_layer] >= temp_sp_high:
                        turn_off()
                    elif check_add_conditions(add_conditions, 'turn_off'):
                        turn_off()





        
        
        # Control strategies for the operation of heat pump in cooling mode
        elif self.operation_mode.lower() == 'cooling':

            if (self.T_room > self.T_hp_sp_winter) or ((self.tank_temps['tank0']['sensor_0'] - self.T_room) < 5):
                self.generators['hp_status'] = 'on'

            if self.tank_temps['tank0']['sensor_0'] > 52:
                self.generators['hp_status'] = 'off'

            if self.generators['hp_status'] == 'on':
                if self.T_room > (self.T_hp_sp_surplus+0.5):
                    self.generators['hp_demand'] = 10000000
                else:
                    self.generators['hp_demand'] = 0
                    self.generators['hp_status'] = 'off'
            else:
                self.generators['hp_demand'] = 0

            
        # Adjusting the mass flow rates for hot water tank in the heat pump circuit, when heat pump operates for only
        # a fraction of the time step
        if self.hp_on_fraction is not None and self.hp_cond_m is not None:
            self.hp_in_F = self.hp_on_fraction * self.hp_cond_m
            self.hp_out_F = -self.hp_on_fraction * self.hp_cond_m
 

        # Calculating the heat required from the in-built heating rod of the hot water tank
        if self.T_hr_sp_hwt is not None:
            if self.T_mean_hwt < self.T_hr_sp_hwt:
                self.hwt_hr_P_th_set = (self.hwt_mass * 4184 * (self.T_hr_sp_hwt - self.T_mean_hwt)) / self.step_size
            else:
                self.hwt_hr_P_th_set = 0
        
        # ----------------- Tank balancing flows -----------------------
        if self.no_tanks > 1:
            for link in self.tank_setup:
                src, dst = link.split(':')
                src_tank, src_port = src.split('.')
                dst_tank, dst_port = dst.split('.')
                self.tank_connections[src_tank][f'{src_port}_F'] = 0
                self.residual_flow = sum([flow for port, flow in self.tank_connections[src_tank].items() if '_F' in port ])
                
                if self.residual_flow > 0:
                    # Flow from src to dst
                    self.tank_connections[dst_tank][f'{dst_port}_T'] = self.tank_connections[src_tank][f'{src_port}_T']
                    self.tank_connections[dst_tank][f'{dst_port}_F'] = self.residual_flow #inflow
                    self.tank_connections[src_tank][f'{src_port}_F'] = -self.residual_flow #outflow
                else:
                    # Flow from dst to src
                    self.tank_connections[src_tank][f'{src_port}_T'] = self.tank_connections[dst_tank][f'{dst_port}_T']
                    self.tank_connections[src_tank][f'{src_port}_F'] = -self.residual_flow #inflow
                    self.tank_connections[dst_tank][f'{dst_port}_F'] = self.residual_flow #outflow

        for tank, vals in self.tank_connections.items():
            self.netflow = sum([flow for port, flow in vals.items() if '_F' in port ])
            if abs(self.netflow) > 1e-5:
                raise ValueError(f"{tank} netflow error!")

        # ----------(in development) For circular connections(linear solving)----------
        
        #Preparing the incidence matrix and calculating residual flows for all tanks.
        # A = np.zeros((self.no_tanks, len(self.tank_setup))) #The incidence matrix
        # self.residuals_flows = {}
        # for i, edge in enumerate(self.tank_setup):
        #     src, dst = edge.split(':')
        #     src_tank, src_port = src.split('.')
        #     dst_tank, dst_port = dst.split('.')
            
        #     A[self.tanks.index(src_tank), i] = -1
        #     A[self.tanks.index(dst_tank), i] = 1
        #     # The rows of the tanks will be in the same order as in tanks list. This will be order of the solved flows.

        #     self.tank_connections[src_tank][f'{src_port}_F'] = 0 #Resetting previous flow values
        #     self.residuals_flows[src_tank] = sum([flow for port, flow in self.tank_connections[src_tank].items() if '_F' in port ])
            
        #     #Sample incidence matrix
        #     '''
        #     tanks\edges | tank0.heat_out:tank1.hp_out | tank1.heat_out:tank2.hp_out
        #     tank0   |            -1                 |            0  
        #     tank1   |             1                 |           -1
        #     tank2   |             0                 |            1
        #     '''
            
        # # converting to numpy array for solving   
        # b = np.array([self.residuals_flows.get(tank, 0) for tank in self.tanks]) # So the order is again preserved.

        # # Solving using least squares method(since, A might not always be a full matrix with a valid inverse)
        # '''
        # If A was a full matrix.
        # F = A^-1 * b
        # But not always A is a full matrix, so least squares method used, which 
        # involved finding a pseudo inverse, and then multiplying with b.
        # '''
        # # so, A* F = b; to solve for F(the balancing flows)
            
        # #F, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
        # F, *_ = np.linalg.lstsq(A, b, rcond=None) # *_ captures the other returned values which are not needed here.
        # # Updating tank_connections with the balancing flows

        # for j, edge in enumerate(self.tank_setup):
        #     src, dst = edge.split(':')
        #     src_tank, src_port = src.split('.')
        #     dst_tank, dst_port = dst.split('.')

        #     # flow_idx = self.tanks.index(src_tank)
        #     flow_val = float(F[j])

        #     if flow_val > 0:
        #         # Flow from src to dst
        #         self.tank_connections[dst_tank][f'{dst_port}_T'] = self.tank_connections[src_tank][f'{src_port}_T']
        #         self.tank_connections[dst_tank][f'{dst_port}_F'] = flow_val
        #         self.tank_connections[src_tank][f'{src_port}_F'] = -flow_val
        #     else:
        #         # Flow from dst to src
        #         self.tank_connections[src_tank][f'{src_port}_T'] = self.tank_connections[dst_tank][f'{dst_port}_T']
        #         self.tank_connections[src_tank][f'{src_port}_F'] = -flow_val
        #         self.tank_connections[dst_tank][f'{dst_port}_F'] = flow_val

        # for tank, vals in self.tank_connections.items():
        #     for connection, val in vals.items():
        #         if 'F' in connection:
        #             tqdm.write(f'{tank} {connection} : {val}')
        
        
        # for tank, vals in self.tank_connections.items():
        #     self.netflow = sum([flow for port, flow in vals.items() if '_F' in port ])
        #     if abs(self.netflow) > 1e-5:
        #         raise ValueError(f"{tank}:{self.netflow} netflow error!")

        # for tank, vals in self.tank_connections.items():
        #     for connection, val in vals.items():
        #         if 'F' in connection:
        #             tqdm.write(f'{tank} {connection} : {val}')

    
    def supply_temp(self, out_temp, buildingtype):
        # largely based on npro guidelines.
        self.heating_curves = {
            "radiator_low_insulation": {"T_out": [-10, 15], "T_supply": [75, 45], "delta_T": 20},
            "radiator_high_insulation": {"T_out": [-10, 15], "T_supply": [55, 35], "delta_T": 15},
            "floor_low_insulation": {"T_out": [-10, 15], "T_supply": [45, 25], "delta_T": 5},
            "floor_high_insulation": {"T_out": [-10, 15], "T_supply": [35, 20], "delta_T": 5}
        }

        curve = self.heating_curves[buildingtype]
        Tsupply = np.interp(out_temp, curve['T_out'], curve['T_supply'])
        # Treturn = Tsupply - curve['delta_T']
        return Tsupply, curve['delta_T']
    
    
    def calc_heat_supply(self, config):
        """Calculate the mass flows and temperatures of water, and the heat from the back up heater in the space
        heating (SH) circuit"""
        
        if config == '2-runner':

            try:
                self.tank_connections['tank0']['heat_in_F'] = self.heat_demand/ (4184 * self.heat_dT)
            except ZeroDivisionError:
                self.tank_connections['tank0']['heat_in_F'] = 0

            self.tank_connections['tank0']['heat_in_F'] = max(0,self.tank_connections['tank0']['heat_in_F'])
            self.tank_connections['tank0']['heat_in_F'] = min(self.max_flow,self.tank_connections['tank0']['heat_in_F'])

            self.heat_supply = self.tank_connections['tank0']['heat_in_F'] * 4184 * self.dhw_Tdelta

            if self.idealheater == 'on':
                self.tank_connections['tank0']['heat_in_F'], self.IdealHrodsum = self.hr.step(self.tank_connections['tank2']['heat_out_T'], self.heat_demand,self.T_dhw_sp, self.dhw_out_T - self.dhw_Tdelta)
                self.tank_connections['tank2']['heat_out_T'] = self.T_dhw_sp
                self.heat_supply = self.heat_demand

            self.tank_connections['tank0']['heat_in_T'] = self.tank_connections['tank2']['heat_out_T'] - self.dhw_Tdelta

            self.tank_connections['tank2']['heat_out_F'] = -self.tank_connections['tank0']['heat_in_F']
            
            self.dhw_supply, self.sh_supply = 0,0
        

        if config == '3-runner' or config == '4-runner':
            
            # Space heating :
            sh_out = f"tank_connections.{self.sh_out}"
            if self.sh_out2: 
                sh_out2 = f"tank_connections.{self.sh_out2}" #using the dhw tank as the hotter tank!
            else:
                sh_out2 = None
            building = 'radiator_high_insulation' #TODO move this to the params
            Tsup, Tdelta = self.supply_temp(self.T_amb, building) #from heating curve
            # using Tdelta to calculate Tretun, and then updating it if incase T supply changes
            self.heat_dT_sh = Tdelta

            self.req_shTsup = Tsup # only for debugging
            
            try:
                sh_F = self.sh_demand/ (4184 * self.heat_dT_sh)  #total flow rate
            except ZeroDivisionError:
                sh_F = 0 #unlikely in current setup, but if return temp delta not fixed, then maybe

            sh_T = helpers.get_nested_attr(self, sh_out+'_T')   #temp of the colder tank
            sh2_T = helpers.get_nested_attr(self, sh_out2+'_T') if sh_out2 else None

            fhot, fcold, Tsup = self.tcvalve1.get_flows(sh2_T, sh_T, Tsup, sh_F, Tdelta) #required flow rates from each of the tanks
            # tqdm.write(f'fhot:{fhot}, fcold:{fcold}')
            sh_F = fhot+fcold #flow rate could be changed if cold tank warmer than req. supply temp
            self.sh_supply = sh_F * 4184 * Tdelta

            Tret = Tsup - Tdelta

            if self.idealheater == 'on':
                new_flow, self.P_hr_sh = self.hr.step(sh2_T, self.sh_demand, Tsup, Tret)
                if self.P_hr_sh > 0:
                    sh2_T = Tsup
                    fhot = new_flow
                    #assume, the hotter tank(dhw tank) will be given more priority.
                    fcold = 0
                    self.sh_supply = self.sh_demand

            if (self.sh_supply - self.sh_demand) < -1:
                tqdm.write(f'Deficit : {self.sh_supply - self.sh_demand}')

            #setting corresponding flow rates
            helpers.set_nested_attr(self, sh_out+'_F', -fcold)
            helpers.set_nested_attr(self, sh_out2+'_F', -fhot)

            # helpers.set_nested_attr(self, sh_out+'_T', sh_T)
            # helpers.set_nested_attr(self, sh_out2+'_T', sh2_T)


            #dhw
            dhw_out = f"tank_connections.{self.dhw_out}"
            self.dhw_out_T = helpers.get_nested_attr(self,dhw_out+'_T')

            try:
                dhw_F = self.dhw_demand/(4184 * self.dhw_Tdelta)
            except ZeroDivisionError:
                dhw_F = 0
            
            dhw_F = max(0,dhw_F)
            dhw_F = min(self.max_flow, dhw_F)
            self.dhw_supply = dhw_F * 4184 * self.dhw_Tdelta

            if self.idealheater == 'on':
                new_flow, self.IdealHrodsum = self.hr.step(self.dhw_out_T, self.dhw_demand, self.T_dhw_sp, self.dhw_out_T - self.dhw_Tdelta)
                if self.IdealHrodsum > 0:
                    self.dhw_out_T = self.T_dhw_sp
                    dhw_F = new_flow
                    self.dhw_supply = self.dhw_demand


            self.IdealHrodsum += self.P_hr_sh
            helpers.set_nested_attr(self, dhw_out+'_F', -dhw_F)
            helpers.set_nested_attr(self, dhw_out+'_T', self.dhw_out_T)

            self.dhw_rT = self.dhw_out_T - self.dhw_Tdelta

            if config == '3-runner':
                # self.tank_connections[self.ret_tank]['heat_in_F'] = dhw_F + sh_F 
                # self.tank_connections[self.ret_tank]['heat_in_T'] = (self.heat_rT*dhw_F + Tret*sh_F)/(dhw_F+sh_F) if (dhw_F+sh_F) != 0 else 0
                helpers.set_nested_attr(self, f"tank_connections.{self.ret_tank}_F", dhw_F + sh_F)
                helpers.set_nested_attr(self, f"tank_connections.{self.ret_tank}_T", (self.dhw_rT*dhw_F + Tret*sh_F)/(dhw_F+sh_F) if (dhw_F+sh_F) != 0 else 0)
            elif config == '4-runner':
                helpers.set_nested_attr(self, f"tank_connections.{self.sh_ret}_F", sh_F)
                helpers.set_nested_attr(self, f"tank_connections.{self.sh_ret}_T", Tret)

                helpers.set_nested_attr(self, f"tank_connections.{self.dhw_ret}_F", dhw_F)
                helpers.set_nested_attr(self, f"tank_connections.{self.dhw_ret}_T", self.dhw_rT)
            # tqdm.write(f'calculated  temps : {Tsup}, return {Tret}')
            # tqdm.write(f'calculated  flows tank2 : {fhot}, tank1 {fcold}')

            

class TCValve():
    def __init__(self, max):
        """
    A simplified model of a temperature-controlled 3-way mixing valve.

    The valve mixes flow between two tanks (hot and cold) to achieve a desired 
    supply temperature `T`, while respecting a maximum flow rate restriction 
    for each source.

    Parameters
    ----------
    max : float
        The maximum flow rate allowed from either the hot or cold tank [kg/s or L/s].
        """
        self.maxflow = max
        

    def get_flows(self, Thot, Tcold, T, flow, dT):
        """
        Calculate the required hot and cold flows to achieve the target temperature.

        Parameters
        ----------
        Thot : float
            Temperature of the hot tank [°C].
        Tcold : float
            Temperature of the cold tank [°C].
        T : float
            Target (mixed) supply temperature [°C].
        flow : float
            Total requested flow rate [kg/s or L/s].
        dT : float
            Temperature difference between suppy and return lines.

        Returns
        -------
        f_hot : float
            Flow rate from the hot tank [kg/s or L/s].
        f_cold : float
            Flow rate from the cold tank [kg/s or L/s].
        T_sup : float
            Actual supply temperature achieved after mixing [°C].
        """
        if flow == 0:
            return 0,0,0
        Tret = T - dT # Return temperature if supply is at the heating curve determined temperature.
        if Thot is None:
            f_hot, f_cold, T_sup = 0, flow, Tcold
            return f_hot, f_cold, T_sup 
        
        if Tcold > T:
            # If even the cold tank, warmer than req. supply temp, then all flow from this tank, and flow rate decreased accordingly.
            # flow*(T-Tret)*cp = demand, demand/(cp*dT) = flow_new, at the new supply temperature
            f_cold = flow*(T - Tret) / dT
            T_sup = Tcold
            # f_cold = flow
            f_hot = 0
            return f_hot, f_cold, T_sup
        
        #If both tanks are colder than req. supply temp.
        if Thot < T and Tcold < T:
            f_hot = flow*(T - Tret) / dT
            T_sup = Thot
            f_cold = 0
            return f_hot, f_cold, T_sup


        try:
            if Thot == Tcold:
                ratio_hot = 1 #all the flow from the hotter tank.
                T_sup = Thot
            else:
                ratio_hot = (T - Tcold)/(Thot - Tcold)
                T_sup  = T

            f_hot = flow*ratio_hot
            f_cold = flow * (1-ratio_hot)

            if f_hot > self.maxflow and f_cold > self.maxflow:
                tqdm.write(f'limitting {f_hot, f_cold} to {self.maxflow}')
                f_hot, f_cold = self.maxflow, self.maxflow
                

            elif f_hot > self.maxflow:
                tqdm.write(f'limitting {f_hot} to {self.maxflow}')
                f_hot = self.maxflow
                f_cold = (T*flow - f_hot*Thot)/Tcold

            elif f_cold > self.maxflow:
                tqdm.write(f'limitting {f_cold} to {self.maxflow}')
                f_cold = self.maxflow
                f_hot = (T*flow - f_cold*Tcold)/Thot
        except ZeroDivisionError:
            f_hot,f_cold = 0,0

        T_sup = (Thot*f_hot + Tcold*f_cold)/(f_hot+f_cold)

        return f_hot, f_cold, T_sup

        
class idealHeatRod():
    """
    Ideal electric heating rod model.

    This class simulates an idealized heating rod that heats water
    up to a given domestic hot water (DHW) setpoint temperature.
    The heating rod is assumed to have no losses and infinite ramp rate.

    Can be very useful in quanitify supply deficit.
    """
    def __init__(self, setpoint = None, returntemp = None):
        """
        Initialize the heating rod model.

        Parameters
        ----------
        setpoint(optional) : float
            Desired setpoint temperature [°C]. Fixed value, e.g Drinking Hot watar setpoint
        returntemp(optional) : float
            (fixed)Reference return water temperature [°C].
        """
        self.dhw_sp = setpoint
        self.rT = returntemp
        self.cp = 4184

    def step(self, temp, demand, sup_setTemp = None, ret_setTemp = None):
        """
        Compute the required power to achieve desired temp and the power required.

        Parameters
        ----------
        temp : float
            Current outlet water temperature [°C].
        demand : float
            Required thermal energy demand [kW] for this timestep.
        sup_setTemp(optional) : float
            Determined supply temperature(heating curve). Either passed as argument here, or initialised with object.
        ret_setTemp(optional) : float
            Determined return temperature. Either passed as argument here, or initialised with object.

        Returns
        -------
        flow : float
            Required mass flow rate [kg/s] to satisfy the demand.
        P : float
            Instantaneous heating power [W] supplied by the rod.
        """
        if sup_setTemp is None or ret_setTemp is None:
            if self.dhw_sp and self.rT:
                sup_setTemp = self.dhw_sp
                ret_setTemp = self.rT
            else :
                raise IncompleteConfigError("Determined temp not specified!\nNeeds to be either set at Heater object initialization or passed as argument to this method!! ")
        
        # Assuming a 5k tolerance, this case intended for space heating, exact outflow temp is not important.
        #If outflow temp lower than tolerance, deficit to achieve determined temp calc here.
        if temp < sup_setTemp - 5:
            flow = demand/ (self.cp * (sup_setTemp - ret_setTemp))
            P = flow * self.cp * (sup_setTemp - temp)
        else:
            flow = demand/ (self.cp * (temp - ret_setTemp))
            P = 0 

        return flow, P 


class IncompleteConfigError(Exception) : pass
# %%
