__doc__ = """
The controller module contains an updated class for the controller model (:class:`Controller`).
"""
#Logging setup------------------------------------------------------------------------------------------------------------#
# import logging

# logger_controller = logging.getLogger("mosaik_logger")
# logger_controller.setLevel(logging.DEBUG)  # Log everything (DEBUG, INFO, WARNING, ERROR)

# # Create a file handler to store logs
# file_handler_controller = logging.FileHandler("controller_mosaik_simulation.log")  # Save to file
# file_handler_controller.setLevel(logging.DEBUG)

# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.INFO)

# logger_controller.addHandler(file_handler_controller)
#----------------------------------------------------------------------------------------------------------------------------#

import pandas as pd
import numpy as np
from tqdm import tqdm
from des_sim.utils import helpers

import operator
import warnings

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
        
    def __init__(self, params, *, warn: bool = True):

        
        self.validate_params(params, warn=warn)
        # --------------------------------Initialising attributes from params----------------------------------------------
        # Control mode
        self.operation_mode = params.get('operation_mode', 'heating')
        self.control_strategy = params.get('control_strategy', '1')
        self.idealheater = params.get('Ideal_hr_mode', 'off').lower()
        
        #supply configuration
        self.config = params.get('supply_config')
        self.heating_curve = params.get('heating_curve', 'floor_high_insulation')
        self.sh_out = params.get('sh_out', None)                    # Tank which serves as the Output connection for space heating
        self.sh_out2 = params.get('sh_out2', None)
        self.dhw_out = params.get('dhw_out', None)                  # Tank which serves as the Output connection for hot water demand
        self.dhw_out2 = params.get('dhw_out2', None)
        self.ret_tank = params.get('return_conn', None)             # Tank which serves as the return connection; used except for 4-pipe!!!
        self.sup_tank = params.get('supply_conn', None)             # Connections which serves as the heat out for 2 pipe set up
        self.sh_ret = params.get('sh_ret', None)                    # Tank which serves as the return connection for space heating
        self.dhw_ret = params.get('dhw_ret', None)
        self.dhw_Tdelta = params.get('dhw_Tdelta', 15)              # The temperature difference in the dhw circuit.
        self.T_dhw_sp = params.get('T_dhw_sp', 65)
        self.T_dhn_sp = params.get('T_dhn_sp', None)                # The temperature set point for the distribution, in 2-pipe and 2-pipe-dch setup
        self.heat_dT = params.get('heat_dT', 15)                    # The temperature difference in 2-pipe and 2-pipe-dch setup
        self.params_hwt = params.get('tank')
        self.max_flow = params.get('max_flow', 20)                  # The max flow rate permissible in one step.
        
        self.gens = params.get('gens')
        self.no_tanks = params.get('NumberofTanks')                 # The number of tanks in the system
        self.tank_setup = params.get('TankbalanceSetup', None)      # The tank connections in the system

        self.control_logic = params.get('logic', None) # the control logic dict
        
        # --------------------------------Initialising attributes----------------------------------------------
        
        self.generators = {
            f'{gen}_{suffix}' : init for gen in self.gens for suffix, init in zip(['status', 'demand', 'supply', 'uptime'], ['off', 0, 0, 0])
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
        self.dhw_supply, self.sh_supply, self.heat_supply, self.dch_power = None, None, None, None  # The heat supplied for DHW, SH and total (in W)

        self.hp_in_F = None                 # The mass flow of water into the hot water tank from heat pump (in kg/s)
        self.hp_in_T = None                 # The temperature of water into the hot water tank from heat pump (in °C)
        self.hp_out_F = None                # The mass flow of water from the hot water tank into heat pump (in kg/s)
        self.hp_out_T = None                # The temperature of water from the hot water tank into heat pump (in °C)
        self.hp_cond_m = None               # The mass flow of water in the condenser of heat pump (in kg/s)
        self.hp_on_fraction = None          # The fraction of the time step for which the heat pump is on

        self.chp_uptime = None              #Time since startup of chp
        self.boiler_uptime = None       # The time for which the boiler has been operational (in Seconds)
        
        self.T_mean_hwt = 0              # The mean temperature of the hot water tank (in °C)
        self.hwt_mass = 0                # The total mass of water inside the hot water tank (kg)

        self.hwt_hr_P_th_set = None         # The heat demand for the in built heating rod of the hot water tank (in W)

        self.IdealHrodsum = 0           # The sum of P_hr and space heating idealheater
        self.P_hr_sh = 0                #Instantatus of Ideal heater only for space heating.
        self.tcvalve1 = TCValve(self.max_flow)
        if self.config in ['3-pipe', '4-pipe']:
            self.tcvalve2 = TCValve(self.max_flow) if self.dhw_out2 is not None else None
        self.hr = idealHeatRod()

        for i in range(self.no_tanks):              # Inbuilt heating rod demand per tank, initialised to 0.
            setattr(self, f"hwt{i}_hr_1", 0)

        
        self.rod_tanks = params.get("rod_tanks", [f"tank{self.no_tanks - 1}"]) # Which tanks actually have a heating rod. Default: only the last tank.

        self.pv_gen = None
        self.chp_el = None  # The electricity generation from the chp
        self.HP_P_Required = None # The power requirement of the heat pump
        self.battery_soc = None # The state of charge of the battery
        self.charge_battery = None # The power to charge the battery [W]
        self.discharge_battery = None # The power to discharge the battery [W]

        self.pred_el_demand = None #The predicted/future electricity demand.
        
        self.timestamp = None
        self.hp_surplus = False
        self.battery_full = False

        self.HP3wv_out1_share = 1 #The share of the flow from the mixing valve going to output 1(tank 1)

    def get_init_attrs(self):
        '''
        Simply returns a list of all user defined attributes in this class. 
        Useful to add to the attrs list in META.
        '''
        attr_list = helpers.flatten_attrs(self, list(vars(self).keys()))
        return attr_list
    
    def step(self, time):
        """
        Perform a simulation step.
        time: Current simulation time (useful for debugging).

        - Updates kW inputs to W,
        - Sets generator status and demand based on tank sensor temperatures and thresholds defined in dictionary `logic`.
        - Calculates the flow rate and temperature provided for the consumer(SH & DHW).
        - Calculates the balancing flows between multiple tanks if applicable.
        - Calculates the power mode for the inbuilt heating rods in tanks(if applicable).
        - Calculates the power of the ideal heater, in case of supply deficits.

        Next steps:
        - Generator minimum runtime
        """
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
        
        if isinstance(self.timestamp, pd.Timestamp): #if timestamp is not provided, (when not requried)
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
        else:
            self.season = None
            self.isday = None

        # collect last 24 hours of ambient temperature data, to determine sh supply temperature from heating curve
        if not hasattr(self, 'T_amb_24h'):
            self.T_amb_24h = []
        self.T_amb_24h.append(self.T_amb)
        n_24h = int((24*60*60) / self.step_size)
        self.T_amb_24h = self.T_amb_24h[-n_24h:]
        self.T_amb_24h_mean = np.mean(self.T_amb_24h)

        # ---------------------HP charge tank, 3 way valve--------------------------------------
        if self.season == 'summer':
            self.HP3wv_out1_share = 0 # all to tank 2(dhw tank)
        else:
            self.HP3wv_out1_share = 1 # to tank tank1 (middle, SH)

        if 'tank1' in self.tank_temps.keys():
            if self.tank_temps['tank1']['sensor_1'] < 40:
                self.HP3wv_out1_share = 1 # if temp drops too low, switch it back to middle tank

        
        # ------------------HP surplus mode -----------------------------------------
        
        # if surplus electricity generation:
        self.total_gen = (self.pv_gen or 0) + (self.chp_el or 0) - (self.pred_el_demand or 0)

        if (self.pv_gen is not None or self.chp_el is not None) and self.pred_el_demand is not None:
            if self.total_gen > 1 : 
                self.hp_surplus = "True"
            else:
                self.hp_surplus = "False"
        # ------------------battery -----------------------------------------

        if self.battery_soc is not None:
            if self.battery_soc >= 99.5:
                self.battery_full = "True"
            else:
                self.battery_full = "False"
        
        battery_surplus = self.total_gen - self.HP_P_Required
        if battery_surplus > 0 and self.battery_full == "False":
            self.charge_battery = battery_surplus
        else:
            self.charge_battery = 0
        
        # Calculate the mass flows, temperatures and heat from back up heater for the SH circuit
        self.calc_heat_supply(self.config)

        # --------------------------------------------------Inbuilt heating rods P required------------------

        # self.tankLayer_volume = 3.14 * self.params_hwt['height'] * (self.params_hwt['diameter']/2e3)**2  #height is in mm, so H/10^3 * density 1000kg/m3; so density omitted here!
        self.tankLayer_mass = self.params_hwt['volume'] * 1 / self.params_hwt['n_layers'] #1L = 1Kg
        
        # Reset all per-tank heating rod demands to 0 each step.
        for i in range(self.no_tanks):
            setattr(self, f"hwt{i}_hr_1", 0)

        heating_rods = self.params_hwt.get('heating_rods', {})
        if 'hr_1' in heating_rods:
            rod_cfg = heating_rods['hr_1']

            layer_height = self.params_hwt['height'] / self.params_hwt['n_layers']
            rod_layer = min(
                int(rod_cfg['pos'] // layer_height),
                self.params_hwt['n_layers'] - 1,
            )
            sensor_key = f"sensor_{rod_layer}"

            for tank in self.rod_tanks:
                if tank not in self.tanks:
                    continue
                tank_idx = self.tanks.index(tank)
                if (rod_cfg.get('mode') == 'on'
                        and self.tank_temps[tank][sensor_key] < rod_cfg['T_max']):
                    demand = (self.tankLayer_mass * 4184
                            * (rod_cfg['T_max'] - self.tank_temps[tank][sensor_key]))
                    setattr(self, f"hwt{tank_idx}_hr_1", demand)

        # ------------------------------------------Control strategies for the operation of heat pump in heating mode
        if self.operation_mode.lower() == 'heating':
            #Datasheet logic control
            if self.control_strategy == '1':

                # new nested logic dict
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
                        'add_conditions' :{ #this would have higher priority, can override the turn on/off temps.
                            'turn_on' : {'attr' : [sign(default = '<='), thresh_val]},
                            'turn_off' : , 
                        }
                '''
                # Could move these as well, somewhere common, the logic dict could be defined in main_sim, but later
                operatormapping = {
                    '<': operator.lt,
                    '>': operator.gt,
                    '<=': operator.le,
                    '>=': operator.ge,
                    '==': operator.eq,
                }
                
                logic = self.control_logic

                # could move these methods to __init__, but would decrease readability, with very little to no performance impact.
                def turn_on():
                    '''
                    Turns on the generator by setting the appropriate status and demand values.
                    '''
                    self.generators[f'{gen}_status'] = 'on'
                    self.generators[f'{gen}_demand'] = self.hwt_mass * 4184 * (temp_sp_low - self.tank_temps[tank_id][tank_layer]) / self.step_size
                    if self.hwt_mass == 0 or self.hwt_mass is None:
                        warnings.warn("HWT mass is zero or None, cannot calculate generator demand accurately.")
                def turn_off():
                    '''
                    Turns off the generator by setting the appropriate status and demand values.
                    '''
                    self.generators[f'{gen}_status'] = 'off'
                    self.generators[f'{gen}_demand'] = 0

                def check_add_conditions(add_cond_dict, key):
                    '''
                    Checks the additional conditions. Returns true if the condition is satisfied.
                    add_cond_dict: dict containing the additional conditions
                    key: 'turn_on' or 'turn_off'
                    Returns:
                        bool: True if the additional condition is satisfied, False otherwise.

                    '''
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
                        if op_func(helpers.get_nested_attr(self, cond_2), thresh_val): # operator.le(self.T_amb, thresh_val):
                            return True
                    return False

                
                for gen_, cond in logic.items():
                    #gen_ will be the exact key in the dict, with the dhw, sh suffix and such.

                    turn_on_cfg = cond.get('turn_on', {})
                    tank_id = turn_on_cfg.get('tank')
                    tank_layer = turn_on_cfg.get('layer')
                    temp_sp_low = turn_on_cfg.get('turn_on_temp')

                    turn_off_tank_id = cond.get('turn_off', {}).get('tank', tank_id) # defaults to the same tank as turn-on condition
                    turn_off_tank_layer = cond.get('turn_off', {}).get('layer', tank_layer)
                    temp_sp_high = cond.get('turn_off', {}).get('turn_off_temp', temp_sp_low + 5 if temp_sp_low is not None else None)

                    add_conditions = cond.get('add_conditions', {})

                    gen = next((base for base in self.gens if gen_.startswith(base)), None)
                    #To find the generator name from the unique list. Finds the first match.
                    
                    if gen is None:
                        raise RuntimeError(f"Generator '{gen_}' not found in self.gens list")
                    
                    if tank_id is None and tank_layer is None: # if no tank temp based setpoint defined
                        if check_add_conditions(add_conditions, 'turn_on'):
                            # assigning valid values to calculate demand
                        
                            temp_sp_low = self.T_dhw_sp # as default set point temperature
                            tank_id = f'tank{len(self.tanks)-1}' #default to last tank
                            tank_layer = 'sensor_2' #default to top layer
                            turn_on()
                            self.generators[f'{gen}_demand'] = 1 # W
                    else:
                        # Turn on logic
                        if self.tank_temps[tank_id][tank_layer] <= temp_sp_low:
                            turn_on()
                        elif check_add_conditions(add_conditions, 'turn_on'): # this can overwrite the previous temp setpoints
                            turn_on()
                            self.generators[f'{gen}_demand'] = 1 # W
                                    
                    if turn_off_tank_id is None and turn_off_tank_layer is None: # if no tank temp based setpoint defined
                        if check_add_conditions(add_conditions, 'turn_off'):
                            turn_off()
                    else:
                        # Turn off logic
                        if self.tank_temps[turn_off_tank_id][turn_off_tank_layer] >= temp_sp_high:
                            turn_off()
                        elif check_add_conditions(add_conditions, 'turn_off'):
                            turn_off()

            
        # Adjusting the mass flow rates for hot water tank in the heat pump circuit, when heat pump operates for only
        # a fraction of the time step
        if self.hp_on_fraction is not None and self.hp_cond_m is not None:
            self.hp_in_F = self.hp_on_fraction * self.hp_cond_m
            self.hp_out_F = -self.hp_on_fraction * self.hp_cond_m

        # discharging the battery only when battery is full and HP is running
        if self.battery_full == "True":
            self.charge_battery = 0
            if self.generators['hp_status'] == 'on':
                self.discharge_battery = self.HP_P_Required
            else:
                self.discharge_battery = 0
        else:
            self.discharge_battery = 0

        # ----------------- Tank balancing flows -----------------------
        if self.tank_setup is not None:
            tol = 1e-9

            # Reset balancing endpoints and build the link graph
            link_adjacency = {tank: set() for tank in self.tanks}
            for link in self.tank_setup:
                left, right = link.split(':')
                left_tank, left_port = left.split('.')
                right_tank, right_port = right.split('.')
                self.tank_connections[left_tank][f'{left_port}_F'] = 0.0
                self.tank_connections[right_tank][f'{right_port}_F'] = 0.0
                link_adjacency[left_tank].add(right_tank)
                link_adjacency[right_tank].add(left_tank)

            # Compute residuals once after reset
            residuals = {
                tank: sum(flow for key, flow in vals.items() if key.endswith('_F'))
                for tank, vals in self.tank_connections.items()
            }

            # Rerun passes until nothing moves; cascades resolve across passes
            for i in range(len(self.tank_setup) + 1):
                flow_moved = False

                for link in self.tank_setup:
                    left, right = link.split(':')
                    left_tank, left_port = left.split('.')
                    right_tank, right_port = right.split('.')

                    left_res = residuals[left_tank]
                    right_res = residuals[right_tank]

                    # Decide donor and receiver based on residual signs
                    donor_tank = donor_port = recv_tank = recv_port = None
                    flow = 0.0

                    if left_res > tol and right_res < -tol:
                        # left has surplus, right has deficit
                        donor_tank, donor_port = left_tank, left_port
                        recv_tank, recv_port = right_tank, right_port
                        flow = min(left_res, -right_res)
                    elif right_res > tol and left_res < -tol:
                        # right has surplus, left has deficit
                        donor_tank, donor_port = right_tank, right_port
                        recv_tank, recv_port = left_tank, left_port
                        flow = min(right_res, -left_res)
                    elif left_res > tol and abs(right_res) <= tol:
                        # left has surplus, right is neutral: push only if a
                        # deficit can be reached through right (cascade)
                        if self._deficit_reachable(right_tank, link_adjacency, residuals, tol):
                            donor_tank, donor_port = left_tank, left_port
                            recv_tank, recv_port = right_tank, right_port
                            flow = left_res
                    elif right_res > tol and abs(left_res) <= tol:
                        # right has surplus, left is neutral: same idea, mirrored
                        if self._deficit_reachable(left_tank, link_adjacency, residuals, tol):
                            donor_tank, donor_port = right_tank, right_port
                            recv_tank, recv_port = left_tank, left_port
                            flow = right_res

                    if donor_tank is None or flow <= tol:
                        continue

                    # Apply the transfer and keep residuals in sync
                    self.tank_connections[recv_tank][f'{recv_port}_T'] = self.tank_connections[donor_tank][f'{donor_port}_T']
                    self.tank_connections[recv_tank][f'{recv_port}_F'] += flow
                    self.tank_connections[donor_tank][f'{donor_port}_F'] -= flow
                    residuals[donor_tank] -= flow
                    residuals[recv_tank] += flow
                    flow_moved = True

                if not flow_moved:
                    break

        for tank, vals in self.tank_connections.items():
            self.netflow = sum([flow for port, flow in vals.items() if '_F' in port ])
            if abs(self.netflow) > 1e-5:
                raise ValueError(f"{tank} netflow error!")

    
    def _deficit_reachable(self, start_tank, link_adjacency, residuals, tol):
        """Walk the link graph from start_tank; return True if any reachable
        tank has a deficit residual."""
        visited = {start_tank}
        stack = [start_tank]
        while stack:
            node = stack.pop()
            if residuals[node] < -tol:
                return True
            for neighbor in link_adjacency[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        return False

    def supply_temp(self, out_temp, buildingtype):
        # largely based on npro guidelines.
        self.heating_curves = {
            "radiator_low_insulation": {"T_out": [-10, 15], "T_supply": [75, 45], "delta_T": 20},
            "radiator_high_insulation": {"T_out": [-10, 15], "T_supply": [55, 35], "delta_T": 15},
            "floor_low_insulation": {"T_out": [-10, 15], "T_supply": [45, 25], "delta_T": 5},
            "floor_high_insulation": {"T_out": [-10, 15], "T_supply": [35, 20], "delta_T": 5},
            "DHN_high_insulation": {"T_out": [-10, 15], "T_supply": [45, 35], "delta_T": 15},
            "Durlach_mes" : {"T_out": [0, 10], "T_supply": [60, 52], "delta_T": 15}
        }

        curve = self.heating_curves[buildingtype]
        Tsupply = np.interp(out_temp, curve['T_out'], curve['T_supply'])
        # Treturn = Tsupply - curve['delta_T']
        return Tsupply, curve['delta_T']
    
    
    def calc_heat_supply(self, config):
        """Calculate the mass flows and temperatures of water, and the heat from the back up heater in the space
        heating (SH) circuit"""
        
        if config == '2-pipe' or config == '2-pipe-dch':
            try:
                heat_in_F = self.heat_demand/ (4184 * self.heat_dT)
                if config == '2-pipe-dch':
                    heat_in_F = self.sh_demand/ (4184 * self.heat_dT)
            except ZeroDivisionError:
                heat_in_F = 0

            heat_in_F = min(self.max_flow, max(0,heat_in_F))

            if config == '2-pipe-dch':
                self.sh_supply = heat_in_F * 4184 * self.heat_dT
                self.dch_power = self.dhw_demand / 0.98 #assuming 98% efficiency for the decentralized electric heater
            else:
                self.heat_supply = heat_in_F * 4184 * self.heat_dT

            temp = helpers.get_nested_attr(self, f"tank_connections.{self.sup_tank}_T") #the available temperature in tank

            ret_temp = self.T_dhn_sp - self.heat_dT # Return temp in case of ideal supply temperature

            if config == '2-pipe-dch':
                new_flow, self.IdealHrodsum = self.hr.step(temp, self.sh_demand, self.T_dhn_sp, ret_temp)
            else:
                new_flow, self.IdealHrodsum = self.hr.step(temp, self.heat_demand, self.T_dhn_sp, ret_temp)

            if self.IdealHrodsum > 0:
                temp = self.T_dhn_sp
                heat_in_F = new_flow
                if config == '2-pipe-dch':
                    self.sh_supply = self.sh_demand
                else:
                    self.heat_supply = self.heat_demand
            
            # mixing the hot water from the tank down, using the cold return line from the DHN to the required supply temperature
            fhot, fcold, Tsup = self.tcvalve1.get_flows(temp, (self.T_dhn_sp - self.heat_dT), self.T_dhn_sp, heat_in_F, self.heat_dT) 
            
            helpers.set_nested_attr(self, f"tank_connections.{self.sup_tank}_T", temp) #not passed to tank, but to the visu for supporting calcs
            helpers.set_nested_attr(self, f"tank_connections.{self.sup_tank}_F", -fhot)
            helpers.set_nested_attr(self, f"tank_connections.{self.ret_tank}_F", fhot)
            helpers.set_nested_attr(self, f"tank_connections.{self.ret_tank}_T", Tsup - self.heat_dT)

            if config == '2-pipe':
                self.dhw_supply, self.sh_supply = 0,0
        
        if config == '3-pipe' or config == '4-pipe':
            # Space heating (SH):
            sh_out = f"tank_connections.{self.sh_out}"

            Tsup, Tdelta = self.supply_temp(self.T_amb_24h_mean, self.heating_curve) #from heating curve
            # using Tdelta to calculate Tretun, and then updating it if incase T supply changes
            self.heat_dT_sh = Tdelta

            self.req_shTsup = Tsup # only for debugging
            
            try:
                sh_F = self.sh_demand/ (4184 * self.heat_dT_sh)  #total flow rate
            except ZeroDivisionError:
                sh_F = 0 #unlikely in current setup, but if return temp delta not fixed, then maybe

            sh_T = helpers.get_nested_attr(self, sh_out+'_T')   #temp of the colder tank

            self.sh_supply = sh_F * 4184 * Tdelta

            Tret = Tsup - Tdelta

            donor_T = helpers.get_nested_attr(self, f"tank_connections.{self.dhw_out}_T") \
                    if self.dhw_out2 is not None else None

            if donor_T is not None and sh_T < Tsup and donor_T > sh_T:
                # blend hot DHW water into cold SH-tank water to reach Tsup
                f_dhw_borrow, f_sh_tank, sh_T = self.tcvalve2.get_flows(donor_T, sh_T, Tsup, sh_F, Tdelta)
            else:
                # mixing the hot water from the tank down, using the cold return line from the DHN to the required supply temperature
                f_sh_tank, fcold_sh, Tsup_sh = self.tcvalve1.get_flows(sh_T, Tret, Tsup, sh_F, Tdelta) #required flow rates from each of the tanks
                f_dhw_borrow = 0.0

            new_flow, self.P_hr_sh = self.hr.step(sh_T, self.sh_demand, Tsup, Tret)
            if self.P_hr_sh > 0:
                sh_T = Tsup
                sh_F = new_flow
                f_sh_tank = new_flow    # heater sits in SH line → full flow comes from SH side
                f_dhw_borrow = 0.0      # no longer borrowing; heater covers it
                self.sh_supply = self.sh_demand      
            
            #setting corresponding flow rates
            helpers.set_nested_attr(self, f"tank_connections.{self.sh_out}_T", sh_T) #not passed to tank, but to the visu for supporting calcs
            helpers.set_nested_attr(self, f"tank_connections.{self.sh_out}_F", -f_sh_tank)
            if self.dhw_out2 is not None:
                helpers.set_nested_attr(self, f"tank_connections.{self.dhw_out2}_F", -f_dhw_borrow) 

            # Domestic Hot Water (DHW):
            dhw_out = f"tank_connections.{self.dhw_out}"
            self.dhw_out_T = helpers.get_nested_attr(self,dhw_out+'_T')

            try:
                dhw_F = self.dhw_demand/(4184 * self.dhw_Tdelta)
            except ZeroDivisionError:
                dhw_F = 0
            
            dhw_F = max(0,dhw_F)
            dhw_F = min(self.max_flow, dhw_F)
            self.dhw_supply = dhw_F * 4184 * self.dhw_Tdelta

            new_flow, self.P_hr_dhw = self.hr.step(self.dhw_out_T, self.dhw_demand, self.T_dhw_sp, self.dhw_out_T - self.dhw_Tdelta)
            if self.P_hr_dhw > 0:
                self.dhw_out_T = self.T_dhw_sp
                dhw_F = new_flow
                self.dhw_supply = self.dhw_demand

            # mixing the hot water from the tank down, using the cold return line from the DHN to the required supply temperature
            fhot_dhw, fcold_dhw, Tsup_dhw = self.tcvalve1.get_flows(self.dhw_out_T, (self.T_dhw_sp-self.dhw_Tdelta), self.T_dhw_sp, dhw_F, self.dhw_Tdelta) #required flow rates from each of the tanks
            self.dhw_rT = self.T_dhw_sp - self.dhw_Tdelta

            self.IdealHrodsum = self.P_hr_sh + self.P_hr_dhw 
            helpers.set_nested_attr(self, dhw_out+'_F', -fhot_dhw)
            helpers.set_nested_attr(self, dhw_out+'_T', self.dhw_rT)

            if config == '3-pipe':
                helpers.set_nested_attr(self, f"tank_connections.{self.ret_tank}_F", fhot_dhw + f_sh_tank + f_dhw_borrow)
                helpers.set_nested_attr(self, f"tank_connections.{self.ret_tank}_T",
                    (self.dhw_rT*fhot_dhw + Tret*(f_sh_tank + f_dhw_borrow)) / (fhot_dhw + f_sh_tank + f_dhw_borrow)
                    if (fhot_dhw + f_sh_tank + f_dhw_borrow) != 0 else 0)
            elif config == '4-pipe':
                f_sh_ret = f_sh_tank + f_dhw_borrow

                if self.season == 'summer':
                    # summer: the SH circuit is idle, so its return connection is free.
                    # Route the DHW return through it instead and leave 'dhw_ret' unused.
                    helpers.set_nested_attr(self, f"tank_connections.{self.sh_ret}_F", f_sh_ret + fhot_dhw)
                    helpers.set_nested_attr(self, f"tank_connections.{self.sh_ret}_T",
                        (self.dhw_rT*fhot_dhw + Tret*f_sh_ret) / (fhot_dhw + f_sh_ret)
                        if (fhot_dhw + f_sh_ret) != 0 else 0)

                    helpers.set_nested_attr(self, f"tank_connections.{self.dhw_ret}_F", 0)
                    helpers.set_nested_attr(self, f"tank_connections.{self.dhw_ret}_T", 0) # no flow on this port
                else:
                    helpers.set_nested_attr(self, f"tank_connections.{self.sh_ret}_F", f_sh_ret)
                    helpers.set_nested_attr(self, f"tank_connections.{self.sh_ret}_T", Tret)

                    helpers.set_nested_attr(self, f"tank_connections.{self.dhw_ret}_F", fhot_dhw)
                    helpers.set_nested_attr(self, f"tank_connections.{self.dhw_ret}_T", self.dhw_rT)

    def validate_params(self, params, *, warn: bool = True):
        """
        parameter validation for the controller model. Checks for required parameters, types, value ranges and cross-field logic.
        """
        name = type(self).__name__
        hard_errors = []

        # Loop 1: warnings for defaults
        # default_warnings = {
        #     "heating_value": (
        #         "boiler: 'heating_value' not provided; Boiler will default to 10833.3."
        #     ),
        #     "cp": (
        #         "boiler: 'cp' (specific heat capacity) not provided; Boiler will default to 4187 J/kgK (water)."
        #     ),
        #     "op_stages": (
        #         "boiler: 'op_stages' not provided; Boiler will default to [0, 1] (0% and 100% of nominal power)."
        #     ),
        # }
        # for key, msg in default_warnings.items():
        #     if key not in params:
        #         tqdm.write(msg)

            
        # -------------------- warnings --------------------
        if warn:
            if params.get("logic", None).keys() is not None and params.get("gens", None) is not None:
                for gen in params.get("gens", []):
                    if not any(key.startswith(gen) for key in params["logic"].keys()):
                        tqdm.write(f"- {name}: No logic defined for '{gen}' in 'logic' dict; it will not operate.")
        # -------------------- constraints (dict rules, per-key) --------------------
        rules = {
            # required for this model
            "supply_config": {
                "required": True,
                "types": (str,),
                "pred": lambda v: v in ["2-pipe", "2-pipe-dch", "3-pipe", "4-pipe"],
                "msg": "'supply_config' must be either '2-pipe', '2-pipe-dch', '3-pipe' or '4-pipe'.",
            },
            "NumberofTanks": {
                "required": True,
                "types": (int, np.integer),
                "pred": lambda v: v > 0,
                "msg": "'NumberofTanks' must be an integer > 0 when provided.",
            },
            "gens": {
                "required": True,
                "types": (list, tuple, np.ndarray),
                "pred": lambda v: (len(v) > 0 and all(isinstance(x, (str,)) for x in v)),
                "msg": "'gens' must be a non-empty list/array of strings for eg. ['hp', 'chp', 'boiler'].",
            },
            "logic": {
                "required": True,
                "types": (dict,),
                "pred": lambda v: (len(v) > 0 and all(isinstance(k, str) and isinstance(val, dict) for k, val in v.items())),
                "msg": ("'logic' must be a non-empty dict mapping generator names (strings) to dicts. "
                ),
            },
            "tank": {
                "required": True,
                "types": (dict,),
                "pred": lambda v: (
                    isinstance(v.get("connections", None), dict)
                    and isinstance(v.get("n_sensors", None), (int, np.integer))
                    and isinstance(v.get("volume", None), (int, float, np.number))
                    and isinstance(v.get("n_layers", None), (int, np.integer))
                    # Only validate type if the key exists in the dict:
                    and ("heating_rods" not in v or isinstance(v.get("heating_rods"), dict))
                    # 'height' is only read to locate the rod's layer, so it is
                    # required exactly when an 'hr_1' heating rod is configured:
                    and ("hr_1" not in (v.get("heating_rods") or {})
                         or isinstance(v.get("height", None), (int, float, np.number)))
                ),
                "msg": (
                    "'tank' must be a dict with keys: "
                    "connections (dict), n_sensors (int), volume (number), n_layers (int). "
                    "heating_rods (dict) is optional, but when it defines 'hr_1' "
                    "the tank must also provide height (number, in mm)."
                ),
            },

            # conditionally required params
            "TankbalanceSetup": {
                "required": False,
                "types": (list, tuple, np.ndarray),
                "pred": lambda v: (len(v) > 0 and all(isinstance(x, (str,)) for x in v)),
                "msg": "'TankbalanceSetup' must be a non-empty list/array of strings for eg. ['tank0.heat_out:tank1.hp_out', 'tank1.heat_out:tank2.hp_out'].",
            },

            # optional params
            "operation_mode": {
                "required": False,
                "types": (str,),
                "pred": lambda v: v in ["heating"],
                "msg": "'operation_mode' must be 'heating' when provided.",
            },
            "control_strategy": {
                "required": False,
                "types": (str,),
                "pred": lambda v: v in ["1",],
                "msg": "'control_strategy' must be a string equal to '1' when provided.",
            },
            "heating_curve": {
                "required": False,
                "types": (str,),
                "pred": lambda v: v in ["radiator_low_insulation", "radiator_high_insulation", "floor_low_insulation", "floor_high_insulation", "Durlach_mes", "DHN_high_insulation"],
                "msg": "'heating_curve' must be one of 'radiator_low_insulation', 'radiator_high_insulation', 'floor_low_insulation', 'floor_high_insulation', 'DHN_high_insulation' or 'Durlach_mes' when provided.",
            },
            "rod_tanks": {
                "required": False,
                "types": (list, tuple),
                "pred": lambda v: (
                    len(v) > 0
                    and all(isinstance(x, str) for x in v)
                    and all(x.startswith("tank") for x in v)
                ),
                "msg": "'rod_tanks' must be a non-empty list of tank names like ['tank0', 'tank2'] when provided.",
            },
            "dhw_out2": {
                "required": False,
                "types": (str,),
                "pred": lambda v: v.startswith("tank") and "." in v,
                "msg": "'dhw_out2' must be a tank connection string for the DHW->SH valve when provided.",
            },
            "max_flow": {
                "required": False,
                "types": (int, float, np.number),
                "pred": lambda v: v > 0,
                "msg": "'max_flow' must be a positive number when provided.",
            },
        }

        for key, rule in rules.items():
            required = rule.get("required", False)
            types_ = rule.get("types", None)
            pred = rule.get("pred", None)
            msg = rule.get("msg", f"Invalid '{key}'.")

            if key not in params:
                if required:
                    hard_errors.append(f"{name}: missing required parameter '{key}'.")
                continue

            val = params.get(key, None)
            if val is None:
                if required:
                    hard_errors.append(f"{name}: parameter '{key}' must not be None.")
                continue

            if types_ is not None and not isinstance(val, types_):
                hard_errors.append(f"{name}: {msg}")
                continue

            if pred is not None and not pred(val):
                hard_errors.append(f"{name}: {msg}")

        # -------------------- cross-field required logic --------------------
        supply_config = params.get("supply_config", None)
        rod_tanks = params.get("rod_tanks")
        n_tanks = params.get("NumberofTanks")  

        if supply_config == "2-pipe":
            if params.get("supply_conn", None) is None or params.get("return_conn", None) is None:
                hard_errors.append(f"{name}: 'supply_conn' and 'return_conn' are required for '2-pipe' supply_config.")

            if params.get("T_dhn_sp", None) is None:
                hard_errors.append(f"{name}: 'T_dhn_sp' is required for '2-pipe' supply_config.")

        if supply_config == "3-pipe":
            # FIX: use 'return_conn' key (not 'ret_tank')
            if params.get("sh_out", None) is None or params.get("dhw_out", None) is None or params.get("return_conn", None) is None:
                hard_errors.append(f"{name}: 'sh_out', 'dhw_out' and 'return_conn' are required for '3-pipe' supply_config.")

        if supply_config == "4-pipe": 
            if params.get("sh_out", None) is None or params.get("dhw_out", None) is None or params.get("sh_ret", None) is None or params.get("dhw_ret", None) is None:
                hard_errors.append(f"{name}: 'sh_out', 'dhw_out', 'sh_ret' and 'dhw_ret' are required for '4-pipe' supply_config.")
        
        if rod_tanks is not None and isinstance(n_tanks, int):
            valid_tanks = {f"tank{i}" for i in range(n_tanks)}
            invalid = [t for t in rod_tanks if t not in valid_tanks]
            if invalid:
                hard_errors.append(
                    f"{name}: 'rod_tanks' references nonexistent tanks {invalid}. "
                    f"Valid options are {sorted(valid_tanks)}."
                )
        
        if hard_errors:
            raise IncompleteConfigError(
                f"{name} configuration error(s):\n- " + "\n- ".join(hard_errors)
            )        

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
            Temperature of the hot port (A) [°C].
        Tcold : float
            Temperature of the cold port (B) [°C].
        T : float
            Target (mixed) supply temperature [°C].
        flow : float
            Total requested flow rate at outgoing port (AB) [kg/s or L/s].
        dT : float
            Temperature difference between supply and return lines.

        Returns
        -------
        f_hot : float
            Flow rate into the hot port (A) [kg/s or L/s].
        f_cold : float
            Flow rate into the cold port (B) [kg/s or L/s].
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
        if temp < sup_setTemp - 0.5:
            flow = demand/ (self.cp * (sup_setTemp - ret_setTemp))
            P = flow * self.cp * (sup_setTemp - temp)
        else:
            flow = demand/ (self.cp * (temp - ret_setTemp))
            P = 0 

        return flow, P 


class IncompleteConfigError(Exception) : pass
# %%
