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
        self.T_hp_sp_winter = params.get('T_hp_sp_winter')
        self.T_hp_sp_summer = params.get('T_hp_sp_summer')
        self.T_hp_sp_surplus = params.get('T_hp_sp_surplus')
        self.T_hr_sp_hwt = params.get('T_hr_sp_hwt', None)
        self.T_dhw_sp = params.get('T_dhw_sp', None)
        self.heat_rT = params.get('heat_rT', 20) #Specific to the 2-runner setup
        self.operation_mode = params.get('operation_mode', 'heating')
        self.control_strategy = params.get('control_strategy', '1')
        self.idealheater = params.get('Ideal_hr_mode', 'off').lower()
        self.T_chp_h = params.get('T_chp_h')
        self.boiler_delay = params.get('boiler_delay')
        self.T_dhw_buffer = params.get('T_dhw_buffer', 5)

        self.config = params.get('supply_config')
        self.sh_out = params.get('sh_out')  #Tank which serves as the Output connection for space heating
        self.dhw_out = params.get('dhw_out')##Tank which serves as the Output connection for hot water demand

        self.stepsize = params.get('step_size')
        self.boiler_mode = params.get('boiler_mode','off').lower()
        self.params_hwt = params.get('tank')
    
        #ES 04 controller attributes
        self.tank_temps = {

            'tank0' : {
                'top' : 0.0,
                'middle' : 0.0,
                'bottom' : 0.0,
            },
            'tank1' : {
                'top' : 0.0,
                'middle' : 0.0,
                'bottom' : 0.0,
            },
            'tank2' : {
                'top' : 0.0,
                'middle' : 0.0,
                'bottom' : 0.0,
            }
        }
        # self.gens  = ['hp_1', 'hp_2', 'boiler'] # Stutensee setup
        self.gens = ['hp', 'chp', 'boiler']
        
        #TODO  moves these to the class docstring.
        # Stores the operation status, demand, and actual supplied energy 
        # of all the generators defined in self.gens.
        # Keys look like: "<generator>_status", "<generator>_demand", "<generator>_supply"
        self.generators = {
            f'{gen}_{suffix}' : 'off' for gen in self.gens for suffix in ['status', 'demand', 'supply']
        }
        
        self.tank_connections = {
            'tank0' : {
                f'{port}_{suffix}' : 0 for port in params['tank']['connections'].keys() for suffix in ['T', 'F']
            },
            'tank1' : {
                f'{port}_{suffix}' : 0 for port in params['tank']['connections'].keys() for suffix in ['T', 'F']
            },
            'tank2' : {
                f'{port}_{suffix}' : 0 for port in params['tank']['connections'].keys() for suffix in ['T', 'F']
            }
        }
        self.T_amb = None                   # The ambient air temperature (in °C)
        self.heat_source_T = None           # The temperature of source for the heat pump (in °C)
        self.T_room = None                  # The temperature of the room (used in cooling mode, in °C)

        self.heat_demand = None             # The total heat demand from SH & DHW (in W)
        self.dhw_demand = None
        self.sh_demand = None

        self.dhw_supply, self.sh_supply = None, None
        self.heat_supply = 0             # The total heat supplied by the heating system for SH & DHW (in W)

        self.heat_in_F = None                 # The mass flow of water into the hot water tank from SH circuit (in kg/s)
        self.heat_in_T = None                 # The temperature of water into the hot water tank from SH circuit (in °C)
        self.heat_out_F = None                # The mass flow of water from the hot water tank into SH circuit (in kg/s)
        self.heat_out_T = None                # The temperature of water from the hot water tank into SH circuit (in °C)
        self.heat_dT = None                   # The temeprature difference between heat_in_T and heat_out_T (in K)

        self.hp_in_F = None                 # The mass flow of water into the hot water tank from heat pump (in kg/s)
        self.hp_in_T = None                 # The temperature of water into the hot water tank from heat pump (in °C)
        self.hp_out_F = None                # The mass flow of water from the hot water tank into heat pump (in kg/s)
        self.hp_out_T = None                # The temperature of water from the hot water tank into heat pump (in °C)
        self.hp_cond_m = None               # The mass flow of water in the condenser of heat pump (in kg/s)
        self.hp_on_fraction = None          # The fraction of the time step for which the heat pump is on

        self.chp_in_F = None                 # The mass flow of water into the hot water tank from CHP (in kg/s)
        self.chp_in_T = None                 # The temperature of water into the hot water tank from CHP (in °C)
        self.chp_out_F = None                # The mass flow of water from the hot water tank into CHP (in kg/s)
        self.chp_out_T = None                # The temperature of water from the hot water tank into CHP (in °C)
        self.chp_mdot = None                # The temperature of water from the hot water tank into CHP (in °C)
        self.chp_uptime = None              #Time since startup of chp
        
        self.T_mean_hwt = 0              # The mean temperature of the hot water tank (in °C)
        self.hwt_mass = 0                # The total mass of water inside the hot water tank (kg)

        self.hwt_hr_P_th_set = None         # The heat demand for the in built heating rod of the hot water tank (in W)

        self.boiler_mdot = None         # Boiler mass flow rate (in kg/s)
        self.boiler_uptime = None       # The time for which the boiler has been operational (in Seconds)
        self.boiler_in_F = None
        self.boiler_out_F = None

        self.dt = 0 #Time for how long top layer of Tank 3 below threshold, i.e chp not able to keep up with demand.

        self.max_flow = 20            #The max flow rate permissible in one step.
        self.P_hr = [0,0,0]             # Istantaneous power of the Idealheater #TODO more robust for flexible number of tanks
        self.IdealHrodsum = 0           # The sum of P_hr and space heating idealheater
        self.P_hr_sh = 0                #Instantatus of Ideal heater only for space heating.
        self.tcvalve1 = TCValve(self.max_flow)
        self.hr_dhw = idealHeatRod(self.T_dhw_sp, self.heat_rT)
        self.hr_sh = idealHeatRod()
        self.hwt2_hr_1 = 0 #Inbuilt heatingrods
        self.hwt1_hr_1 = 0
        self.hwt0_hr_1 = 0

        self.pv_gen = None
        self.chp_el = None  #The electricity generation from the chp
        self.HP_P_Required = None #The power requirement of the heat pump

        self.pred_el_demand = None #The predicted/future electricity demand.
        
        self.timestamp = None
        self.hp_surplus = False

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
        self.heat_source_T = self.T_amb
        
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

        if self.tank_connections['tank0']['heat_in_F'] is None :
            self.tank_connections['tank0']['heat_in_F'] = 0
        if self.tank_connections['tank0']['hp_out_F'] is None :
            self.tank_connections['tank0']['hp_out_F'] = 0
        
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
        self.IdealHrodsum = sum(self.P_hr)

        # --------------------------------------------------Inbuilt heating rods P required------------------

        # self.tankLayer_volume = 3.14 * self.params_hwt['height'] * (self.params_hwt['diameter']/2e3)**2  #height is in mm, so H/10^3 * density 1000kg/m3; so density omitted here!
        self.tankLayer_mass = self.params_hwt['volume'] * 1 / self.params_hwt['n_layers'] #1L = 1Kg
        
        # if chaning hr position, change the temp value here as well!
        if self.params_hwt['heating_rods']['hr_1']['mode'] == 'on' and self.tank_temps['tank2']['top'] < self.params_hwt['heating_rods']['hr_1']['T_max']:
            self.hwt2_hr_1 = self.tankLayer_mass * 4184 * (self.params_hwt['heating_rods']['hr_1']['T_max'] - self.tank_temps['tank2']['top'])

        self.hwt1_hr_1, self.hwt0_hr_1 = 0,0 

        # ------------------------------------------Control strategies for the operation of heat pump in heating mode
        if self.operation_mode.lower() == 'heating':
            #Datasheet logic control
            if self.control_strategy == '1':
                                
                
                #-------------------Heat pump----------------
                if self.season == 'winter':

                    if self.tank_temps['tank1']['middle'] < self.T_hp_sp_winter: #Turns on only when below threshold of 35 degrees.
                        
                        self.generators['hp_status'] = 'on'
                        
                    if self.generators['hp_status'] == 'on' and self.isday: # Hp runs until upper threshold achieved.
                        if self.tank_temps['tank0']['bottom'] < self.T_hp_sp_winter:
                            self.generators['hp_demand'] = self.hwt_mass * 4184 * (self.T_hp_sp_winter - self.tank_temps['tank0']['bottom']) / self.step_size
                        
                        elif self.hp_surplus and self.tank_temps['tank0']['bottom'] < self.T_hp_sp_surplus:
                            self.generators['hp_demand'] =  self.hwt_mass * 4184 * (self.T_hp_sp_surplus - self.tank_temps['tank0']['bottom']) / self.step_size
                        
                        else:
                            self.generators['hp_demand'] = 0
                            self.generators['hp_status'] = 'off'
                    elif self.isday == False:
                        if self.tank_temps['tank0']['top'] < self.T_hp_sp_winter:
                            self.generators['hp_demand'] = self.hwt_mass * 4184 * (self.T_hp_sp_winter - self.tank_temps['tank0']['top']) / self.step_size
                        
                        elif self.hp_surplus and self.tank_temps['tank0']['bottom'] < self.T_hp_sp_surplus:
                            self.generators['hp_demand'] =  self.hwt_mass * 4184 * (self.T_hp_sp_surplus - self.tank_temps['tank0']['bottom']) / self.step_size
                            # tqdm.write(f'       In surplus mode! Time :{time}') #Prints without interrupting progress bar.
                        
                        else:
                            self.generators['hp_demand'] = 0
                            self.generators['hp_status'] = 'off'      
                    
                    else:
                        self.generators['hp_demand'] = 0

                if self.season == 'summer':

                    if self.tank_temps['tank2']['middle'] < self.T_hp_sp_summer: #Turns on only when below threshold of 35 degrees.
                        
                        self.generators['hp_status'] = 'on'
                        
                    if self.generators['hp_status'] == 'on' and self.isday: # Hp runs until upper threshold achieved.
                        if self.tank_temps['tank0']['bottom'] < self.T_hp_sp_summer:
                            self.generators['hp_demand'] = self.hwt_mass * 4184 * (self.T_hp_sp_summer - self.tank_temps['tank0']['bottom']) / self.step_size
                                                
                        else:
                            self.generators['hp_demand'] = 0
                            self.generators['hp_status'] = 'off'
                    
                    elif self.isday == False:
                        if self.tank_temps['tank1']['middle'] < self.T_hp_sp_summer:
                            self.generators['hp_demand'] = self.hwt_mass * 4184 * (self.T_hp_sp_summer - self.tank_temps['tank1']['middle']) / self.step_size
                        
                        else:
                            self.generators['hp_demand'] = 0
                            self.generators['hp_status'] = 'off'      
                    
                    else:
                        self.generators['hp_demand'] = 0
                
                if self.generators['hp_status'] == None:
                        self.generators['hp_status'] = 'off'
                    
                #--------------------CHP----------------
                if self.tank_temps['tank2']['top'] < self.T_dhw_sp + self.T_dhw_buffer: #i.e high heat demand
                    self.generators['chp_status'] = 'on'
                    
                
                if self.generators['chp_status'] == 'on': #runs until bottom layer of tank 2 reaches the threshold
                    if self.tank_temps['tank2']['bottom'] < self.T_chp_h:
                        self.generators['chp_demand'] = self.hwt_mass * 4184 * (self.T_dhw_sp - self.tank_temps['tank2']['bottom']) / self.step_size
                    elif self.chp_uptime >= 15: #15 minute minimum runtime
                        self.generators['chp_demand'] = 0
                        self.generators['chp_status'] = 'off'
                    else:
                        self.generators['chp_demand'] = self.hwt_mass * 4184 * (self.T_dhw_sp - self.tank_temps['tank2']['bottom']) / self.step_size

                    # logger_controller.debug(f'time : {time} \tbottom layer : {self.bottom_layer_T_chp}, uptime : {self.chp_uptime}, status : {self.chp_status}')
                else:
                    
                    self.generators['chp_demand'] = 0
                
                #-----------------Boiler------------------
                #If the CHP is not able to keep up :
                # Data transfer only at end of step, so this ensures, dt incremented after one step of chp.
                if self.tank_temps['tank2']['top'] < self.T_dhw_sp and self.chp_uptime > 0: 
                    self.dt += self.step_size
                else :
                    self.dt = 0
                
                if self.dt > self.boiler_delay and self.tank_temps['tank2']['top'] < self.T_dhw_sp and self.boiler_mode == 'on':
                     self.generators['boiler_status'] = 'on'
                    
                
                if self.generators['boiler_status'] == 'on':
                    if self.tank_temps['tank2']['bottom'] < self.T_chp_h:
                        self.generators['boiler_demand'] = self.hwt_mass * 4184 * (self.T_dhw_sp - self.tank_temps['tank2']['bottom']) / (self.step_size * 2) # heat up the entire tank to T_hr_sp in 2 time steps
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

                logic = {
                    #Comp : [tank, layer, turn_on_temp, turn_off, {additional turn on conditions with attribute name and temp value}, {additional turn off conditions}]
                    'hp_dhw' : ['tank1', 'top', 55, 60, {'turn_off' : {'T_amb' : -5}}], # TWW
                    'hp_sh' : ['tank2', 'top', 55, 60, {'turn_off' : {'T_amb' : -5}}],
                    'boiler' : ['tank2', 'top', 58, 65],
                    'chp' : ['tank2', 'top', 58, 65]
                }
                # add_conditions = {
                #     'turn_on' : {'attr' : 'thresh_val'},
                #     'turn_off' : {'attr' : 'thresh_val'}
                # }

                for gen_, cond in logic.items():
                    #gen_ will be the exact key in the dict, with the dhw, sh suffix and such.
                    tank_id = cond[0]
                    tank_layer = cond[1]
                    temp_sp_low = cond[2]
                    temp_sp_high = helpers.safe_get(cond, 3, temp_sp_low+5)
                    add_conditions = helpers.safe_get(cond, 4)

                    gen = next((base for base in self.gens if gen_.startswith(base)), None)
                    #To find the generator name from the unique list. Finds the first match.
                    
                    if gen is None:
                        raise RuntimeError(f"Generator '{gen_}' not found in self.gens list")
                    if self.tank_temps[tank_id][tank_layer] <= temp_sp_low:
                        self.generators[f'{gen}_status'] = 'on'
                        self.generators[f'{gen}_demand'] = self.hwt_mass * 4184 * (temp_sp_low - self.tank_temps[tank_id][tank_layer]) / self.step_size

                    elif add_conditions:
                        if 'turn_on' in add_conditions.keys():
                            for cond_2, thresh in add_conditions['turn_on'].items():
                                if getattr(self, cond_2) <= thresh:
                                    self.generators[f'{gen}_status'] = 'on'
                                    self.generators[f'{gen}_demand'] = self.hwt_mass * 4184 * (temp_sp_low - self.tank_temps[tank_id][tank_layer]) / self.step_size
                    
                    elif self.tank_temps[tank_id][tank_layer] >= temp_sp_high:
                        self.generators[gen] = 'off'
                        self.generators[f'{gen}_demand'] = 0
                    elif add_conditions:
                        if 'turn_off' in  add_conditions.keys():
                            for cond_2, thresh in add_conditions['turn_off'].items():
                                if getattr(self, cond_2) >= thresh:
                                    self.generators[f'{gen}_status'] = 'off'
                                    self.generator[f'{gen}_demand'] = 0





        
        
        # Control strategies for the operation of heat pump in cooling mode
        elif self.operation_mode.lower() == 'cooling':

            if (self.T_room > self.T_hp_sp_winter) or ((self.tank_temps['tank0']['bottom'] - self.T_room) < 5):
                self.generators['hp_status'] = 'on'

            if self.tank_temps['tank0']['bottom'] > 52:
                self.generators['hp_status'] = 'off'

            if self.generators['hp_status'] == 'on':
                if self.T_room > (self.T_hp_sp_surplus+0.5):
                    self.generators['hp_demand'] = 10000000
                else:
                    self.generators['hp_demand'] = 0
                    self.generators['hp_status'] = 'off'
            else:
                self.generators['hp_demand'] = 0

        # Setting the inlet temperature to the hot water tank from the heat pump, in the case where heat pump isn't
        # operational
        if self.hp_in_T is None:
            self.hp_in_T = self.hp_out_T
        
        if self.generators['hp_supply'] is None:
            self.generators['hp_supply'] = 0

        # Do the same as above for the CHP
        if self.chp_in_T is None:
            self.chp_in_T = self.chp_out_T
        
        if self.generators['chp_supply'] is None:
            self.generators['chp_supply'] = 0

        if self.generators['boiler_supply'] is None:
            self.generators['boiler_supply'] = 0
            
        # Adjusting the mass flow rates for hot water tank in the heat pump circuit, when heat pump operates for only
        # a fraction of the time step
        if self.hp_on_fraction is not None and self.hp_cond_m is not None:
            self.hp_in_F = self.hp_on_fraction * self.hp_cond_m
            self.hp_out_F = -self.hp_on_fraction * self.hp_cond_m

        # Do the same for CHP
        if self.chp_mdot is not None:
            self.chp_in_F = self.chp_mdot
            self.chp_out_F = -self.chp_mdot 

        if self.boiler_mdot is not None:
            self.boiler_in_F = self.boiler_mdot
            self.boiler_out_F = -self.boiler_mdot  

        # Calculating the heat required from the in-built heating rod of the hot water tank
        if self.T_hr_sp_hwt is not None:
            if self.T_mean_hwt < self.T_hr_sp_hwt:
                self.hwt_hr_P_th_set = (self.hwt_mass * 4184 * (self.T_hr_sp_hwt - self.T_mean_hwt)) / self.step_size
            else:
                self.hwt_hr_P_th_set = 0
        
        # Calculating the resulting mass flows for the TES the distributing the temperatures and flows to the next TES 
        #! the following functions are specific to this configuration
        # self.tes0_heat_in_F = self.heat_in_F
        self.tank_connections['tank0']['hp_out_F'] = self.hp_out_F
        self.tank_connections['tank1']['hp_in_F'] = self.hp_in_F
        self.tes0_residual_flow = self.tank_connections['tank0']['heat_in_F'] + self.tank_connections['tank0']['hp_out_F'] + self.tank_connections['tank0']['heat_out2_F']

        #If Demand flow < hp flow, the residual flow from tank 0 to 1.
        if self.tes0_residual_flow > 0:
            self.tank_connections['tank1']['hp_out_T'] = float(self.tank_connections['tank0']['heat_out_T'])
            self.tank_connections['tank0']['heat_out_F'] = - self.tes0_residual_flow
            self.tank_connections['tank1']['hp_out_F'] = self.tes0_residual_flow

        else:
            self.tank_connections['tank0']['heat_out_T'] = float(self.tank_connections['tank1']['hp_out_T']) #Flow from 1 to 0.
            self.tank_connections['tank0']['heat_out_F'] = - self.tes0_residual_flow
            self.tank_connections['tank1']['hp_out_F'] = self.tes0_residual_flow

        if self.tank_connections['tank0']['heat_in_F'] + self.tank_connections['tank0']['heat_out_F'] + self.tank_connections['tank0']['hp_out_F'] > 1e-5:
            raise ValueError("Tank-0 netflow error!")
        
        self.tes1_residual_flow = self.tank_connections['tank1']['heat_in_F'] + self.tank_connections['tank1']['hp_in_F'] + self.tank_connections['tank1']['hp_out_F'] + self.tank_connections['tank1']['heat_out2_F']
        # logger_controller.debug(f'tes1 residual flow: {self.tes1_residual_flow}')

        if self.tes1_residual_flow > 0:
            self.tank_connections['tank2']['hp_out_T'] = float(self.tank_connections['tank1']['heat_out_T'])
            self.tank_connections['tank1']['heat_out_F'] = - self.tes1_residual_flow
            self.tank_connections['tank2']['hp_out_F'] = self.tes1_residual_flow

        else:
            self.tank_connections['tank1']['heat_out_T'] = self.tank_connections['tank2']['hp_out_T']
            self.tank_connections['tank1']['heat_out_F'] = - self.tes1_residual_flow
            self.tank_connections['tank2']['hp_out_F'] =  self.tes1_residual_flow

        if self.tank_connections['tank1']['heat_out_F'] + self.tank_connections['tank1']['hp_out_F'] + self.tank_connections['tank1']['hp_in_F'] + self.tank_connections['tank1']['heat_out2_F'] > 1e-5:
            raise ValueError("Tank-1 netflow error!")
        

    def calc_hr_P(self, out_temp, demand):
        """Assuming an ideal heating rod, heats up the outlet connection temp to the setpoint instantaneously and calculates the power req.

        Args:
            flow (_type_): flow rate of the output|heat supply
            out_temp (_type_): temperature of the output connection

        Returns:
            _type_: Returns the heating rod power required and also the updates the output temperature.
        """
        
        results = {'P': 0
                   }
        
        if out_temp < self.T_dhw_sp and self.idealheater == 'on':
            #TODO different returm temps for sh and dhw needed.
            flow = demand / (4184 * (self.T_dhw_sp - self.heat_rT))  #Calculating adjusted flow rated with increased temp.

            P = flow * 4184 * (self.T_dhw_sp- out_temp) #out_temp is the temperature at outlet flow, which is to be heated by the rods.
            out_temp = self.T_dhw_sp
            supply = demand # Heat supplied = demand

            results = {'P': P,
                       'out_temp': out_temp,
                       'flow': flow,
                       'supply': supply
                   }

            return results

        
        return results
    
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
        Treturn = Tsupply - curve['delta_T']
        return Tsupply, Treturn
    
    
    def calc_heat_supply(self, config):
        """Calculate the mass flows and temperatures of water, and the heat from the back up heater in the space
        heating (SH) circuit"""
        
        #attributes to be updated if Heating rod turned on.
        updates = [self.P_hr[2], self.tank_connections['tank2']['heat_out_T'], self.tank_connections['tank0']['heat_in_F'], self.heat_supply]
        outputkeys = ['P', 'out_temp', 'flow', 'supply'] #output keys of the heating rod return dict.
        
        if config == '2-runner':

            self.heat_dT = self.tank_connections['tank2']['heat_out_T'] - self.heat_rT
            try:
                self.tank_connections['tank0']['heat_in_F'] = self.heat_demand/ (4184 * self.heat_dT)
            except ZeroDivisionError:
                self.tank_connections['tank0']['heat_in_F'] = 0

            self.tank_connections['tank0']['heat_in_F'] = max(0,self.tank_connections['tank0']['heat_in_F'])
            self.tank_connections['tank0']['heat_in_F'] = min(self.max_flow,self.tank_connections['tank0']['heat_in_F'])

            self.heat_supply = self.tank_connections['tank0']['heat_in_F'] * 4184 * self.heat_dT

            if self.idealheater == 'on':
                self.tank_connections['tank0']['heat_in_F'], self.P_hr[2] = self.hr_dhw.step(self.tank_connections['tank2']['heat_out_T'], self.heat_demand)
                self.tank_connections['tank2']['heat_out_T'] = self.T_dhw_sp
                self.heat_supply = self.heat_demand

            self.tank_connections['tank0']['heat_in_T'] = self.heat_rT

            self.tank_connections['tank2']['heat_out_F'] = -self.tank_connections['tank0']['heat_in_F']
            
            self.dhw_supply, self.sh_supply = 0,0
        

        if config == '3-runner' or config == '4-runner':
            
            # Space heating :
            sh_out = f"tank_connections.tank{self.sh_out}.heat_out2"
            sh_out2 = f"tank_connections.tank{self.dhw_out}.heat_out2" #using the dhw tank as the hotter tank!
             
            building = 'radiator_high_insulation' #TODO move this to the params
            Tsup, Tret = self.supply_temp(self.T_amb, building) #from heating curve
            self.heat_dT_sh = Tsup - Tret
            
            try:
                sh_F = self.sh_demand/ (4184 * self.heat_dT_sh)  #total flow rate
            except ZeroDivisionError:
                sh_F = 0 #unlikely in current setup, but if return temp delta not fixed, then maybe

            sh_T = helpers.get_nested_attr(self, sh_out+'_T')   #temp of the colder tank
            sh2_T = helpers.get_nested_attr(self, sh_out2+'_T') 
            
            fhot, fcold, Tsup = self.tcvalve1.get_flows(sh2_T, sh_T, Tsup, sh_F, Tret) #required flow rates from each of the tanks
            sh_F = fhot+fcold #flow rate could be changed if cold tank warmer than req. supply temp
            self.sh_supply = sh_F * 4184 * (Tsup - Tret)

            if self.idealheater == 'on':
                new_flow, self.P_hr_sh = self.hr_sh.step(sh2_T, self.sh_demand, Tsup, Tret)
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
            dhw_out = f"tank_connections.tank{self.dhw_out}.heat_out"
            self.dhw_out_T = helpers.get_nested_attr(self,dhw_out+'_T')
            self.heat_dT_dhw = self.dhw_out_T - self.heat_rT
            try:
                dhw_F = self.dhw_demand/(4184 * self.heat_dT_dhw)
            except ZeroDivisionError:
                dhw_F = 0
            
            dhw_F = max(0,dhw_F)
            dhw_F = min(self.max_flow, dhw_F)
            self.dhw_supply = dhw_F * 4184 * self.heat_dT_dhw

            # results_dhw = self.calc_hr_P(self.dhw_out_T, self.dhw_demand)
            if self.idealheater == 'on':
                new_flow, self.P_hr[int(self.dhw_out)] = self.hr_dhw.step(self.dhw_out_T, self.dhw_demand)
                if self.P_hr[int(self.dhw_out)] > 0:
                    self.dhw_out_T = self.T_dhw_sp
                    dhw_F = new_flow
                    self.dhw_supply = self.dhw_demand


            self.P_hr[int(self.dhw_out)] += self.P_hr_sh
            helpers.set_nested_attr(self, dhw_out+'_F', -dhw_F)
            helpers.set_nested_attr(self, dhw_out+'_T', self.dhw_out_T)

            if config == '3-runner':
                self.tank_connections['tank0']['heat_in_F'] = dhw_F + sh_F 
                self.tank_connections['tank0']['heat_in_T'] = (self.heat_rT*dhw_F + Tret*sh_F)/(dhw_F+sh_F)

            elif config == '4-runner':
                self.tank_connections['tank0']['heat_in_F'] = sh_F
                self.tank_connections['tank0']['heat_in_T'] = Tret

                self.tank_connections['tank1']['heat_in_F'] = dhw_F
                self.tank_connections['tank1']['heat_in_T'] = self.heat_rT
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
        

    def get_flows(self, Thot, Tcold, T, flow, Tret):
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
        Tret : float
            Return temperature of the system [°C]. Used to reduce flow if 
            the cold tank is warmer than the target temperature.

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
        
        if Tcold > T:
            # If even the cold tank, warmer than req. supply temp, then all flow from this tank, and flow rate decreased accordingly.
            f_cold = flow*(T - Tret) / (Tcold - Tret)
            T_sup = Tcold
            # f_cold = flow
            f_hot = 0
            return f_hot, f_cold, T_sup
        
        #If both tanks are colder than req. supply temp.
        if Thot < T and Tcold < T:
            f_hot = flow*(T - Tret) / (Thot - Tret)
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
            Required thermal energy demand [J] for this timestep.
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