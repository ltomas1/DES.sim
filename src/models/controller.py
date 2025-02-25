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

        self.T_hp_sp_h = params.get('T_hp_sp_h')
        self.T_hp_sp_l = params.get('T_hp_sp_l')
        self.T_hr_sp_hwt = params.get('T_hr_sp_hwt', None)
        # self.T_hr_sp_chp = params.get('T_hr_sp_chp', None)
        self.T_hr_sp = params.get('T_hr_sp', None)
        # self.heat_dT = params.get('heat_dT', 7)
        self.heat_rT = params.get('heat_rT', 20)
        self.operation_mode = params.get('operation_mode', 'heating')
        self.control_strategy = params.get('control_strategy', '1')
        self.hr_mode = params.get('hr_mode', 'off')

        self.T_amb = None                   # The ambient air temperature (in °C)
        self.heat_source_T = None           # The temperature of source for the heat pump (in °C)
        self.T_room = None                  # The temperature of the room (used in cooling mode, in °C)

        self.heat_demand = None             # The total heat demand from SH & DHW (in W)
        self.heat_supply = None             # The total heat supplied by the heating system for SH & DHW (in W)
        self.hp_demand = None               # The heat demand for the heat pump from the hot water tank (in W)
        self.hp_supply = None               # The heat supplied by the heat pump to the hot water tank (in W)
        self.chp_demand = None              # The heat demand for the CHP from the hot water tank (in W)
        self.chp_supply = None              # The heat supplied by the CHP to the hot water tank (in W)

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
        # self.chp_on_fraction = None          # The fraction of the time step for which the CHP is on
        self.chp_uptime = None              #Time since startup of chp
        
        self.bottom_layer_Tank0 = None       # The temperature of the bottom layer of the hot water tank 0 (in °C)
        self.bottom_layer_Tank2 = None      # The temperature of the bottom layer of the hot water tank 2 (in °C)
        self.top_layer_Tank1 = None             # The temperature of the top layer of the hot water tank 1 (in °C)
        self.top_layer_Tank2 = None              # top layer of tank 2
        self.T_mean_hwt = None              # The mean temperature of the hot water tank (in °C)
        self.hwt_mass = None                # The total mass of water inside the hot water tank (kg)

        self.hwt_hr_P_th_set = None         # The heat demand for the in built heating rod of the hot water tank (in W)

        self.hp_status = None               # The status of the heat pump, either "on" or "off"
        self.chp_status = None               # The status of the CHP, either "on" or "off"

        self.P_hr = None                 # The heat supplied by the back up heater (in W)

        self.boiler_demand = None       # Boiler energy demand determined here, in W 
        self.boiler_supply = None       # Actual supplied boiler energy,
        self.boiler_mdot = None         # Boiler mass flow rate (in kg/s)
        self.boiler_status = None   
        self.boiler_uptime = None       # The time for which the boiler has been operational (in Seconds)
        self.boiler_in_F = None
        self.boiler_out_F = None

        self.dt = 0 #Time for how long top layer of Tank 3 below threshold, i.e chp not able to keep up with demand.

        #TODO write all comments for TES variables 
        self.tes0_heat_out_T = None         # The temperature of the heat_out connection for the tank 0 
        self.tes0_heat_out_F = None         
        self.tes0_heat_in_F = None
        self.tes0_hp_out_F = None

        self.tes1_heat_out_T = None
        self.tes1_heat_out_F = None
        self.tes1_hp_in_F = None
        self.tes1_hp_out_T = None
        self.tes1_hp_out_F = None

        self.tes2_heat_out_F = None
        self.tes2_hp_out_T = None
        self.tes2_hp_out_F = None

        


    def step(self, time):
        """Perform simulation step with step size step_size"""

        # Convert the heat demand available in kW to W
        if self.heat_demand is None or self.heat_demand < 0:
            self.heat_demand = 0
        else:
            self.heat_demand *= 1000

        # Calculate the mass flows, temperatures and heat from back up heater for the SH circuit
        self.calc_heat_supply()

        # Control strategies for the operation of heat pump in heating mode
        if self.operation_mode.lower() == 'heating':

            # Control strategy 1 - start
            if self.control_strategy == '1':
                if self.bottom_layer_Tank0 < self.T_hp_sp_l:
                    self.hp_status = 'on'

                if self.hp_status == 'on':
                    if self.bottom_layer_Tank0 < self.T_hp_sp_h:
                        self.hp_demand = self.hwt_mass * 4184 * (self.T_hp_sp_h - self.bottom_layer_Tank0) / self.step_size
                    else:
                        self.hp_demand = 0
                        self.hp_status = 'off'
                else:
                    self.hp_demand = 0
            # Control strategy 1 - end

            # Control strategy 2 - start
            elif self.control_strategy == '2':
                if self.top_layer_Tank1 < self.T_hp_sp_h:
                    self.hp_status = 'on'
                #
                if self.hp_status == 'off':
                    if self.bottom_layer_Tank0 < self.T_hp_sp_l:
                        self.hp_status = 'on'

                if self.hp_status == 'on':
                    if self.bottom_layer_Tank0 < self.T_hp_sp_l:
                        self.hp_demand = self.hwt_mass * 4184 * (self.T_hp_sp_l - self.bottom_layer_Tank0) / self.step_size
                    else:
                        self.hp_demand = 0
                        self.hp_status = 'off'
                else:
                    self.hp_demand = 0
            # Control strategy 2 - end
            
            # Control strategy 3 - start
            if self.control_strategy == '3':
                self.boiler_demand = 0
                
                if self.bottom_layer_Tank0 < self.T_hp_sp_l: #Turns on only when below threshold of 35 degrees.
                    self.chp_status = 'off'
                    self.hp_status = 'on'
                    
                if self.hp_status == 'on': # Hp runs until upper threshold achieved.
                    if self.bottom_layer_Tank0 < self.T_hp_sp_h:
                        self.hp_demand = self.hwt_mass * 4184 * (self.T_hp_sp_h - self.bottom_layer_Tank0) / self.step_size
                    else:
                        self.hp_demand = 0
                        self.hp_status = 'off'
                else:
                    self.hp_demand = 0

                if self.top_layer_Tank1 < self.T_hp_sp_h: #i.e high heat demand
                    self.chp_status = 'on'
                    self.hp_status = 'off'
                
                if self.chp_status == 'on': #runs until bottom layer of 3 reaches the threshold
                    if self.bottom_layer_Tank2 < self.T_hp_sp_h:
                        self.chp_demand = self.hwt_mass * 4184 * (self.T_hp_sp_h - self.bottom_layer_Tank2) / self.step_size
                    else:
                        self.chp_demand = 0
                        self.chp_status = 'off'
                else:
                    self.hp_demand = 0
                    self.chp_demand = 0
            # Control strategy 3 - end

            #Datasheet logic control
            if self.control_strategy == '5':
                                
                if self.bottom_layer_Tank0 < self.T_hp_sp_l: #Turns on only when below threshold of 35 degrees.
                    
                    self.hp_status = 'on'
                    
                if self.hp_status == 'on': # Hp runs until upper threshold achieved.
                    if self.bottom_layer_Tank0 < self.T_hp_sp_h:
                        self.hp_demand = self.hwt_mass * 4184 * (self.T_hp_sp_h - self.bottom_layer_Tank0) / self.step_size
                    else:
                        self.hp_demand = 0
                        self.hp_status = 'off'
                else:
                    self.hp_demand = 0

                if self.top_layer_Tank2 < self.T_hp_sp_h: #i.e high heat demand
                    self.chp_status = 'on'
                    
                
                if self.chp_status == 'on': #runs until bottom layer of tank 2 reaches the threshold
                    if self.bottom_layer_Tank2 < self.T_hp_sp_h:
                        self.chp_demand = self.hwt_mass * 4184 * (self.T_hp_sp_h - self.bottom_layer_Tank2) / self.step_size
                    elif self.chp_uptime >= 15: #15 minute minimum runtime
                        self.chp_demand = 0
                        self.chp_status = 'off'
                    # logger_controller.debug(f'time : {time} \tbottom layer : {self.bottom_layer_T_chp}, uptime : {self.chp_uptime}, status : {self.chp_status}')
                else:
                    
                    self.chp_demand = 0
                
                #If the CHP is not able to keep up :
                # Data transfer only at end of step, so this ensures, dt incremented after one step of chp.
                if self.top_layer_Tank2 < self.T_hp_sp_h and self.chp_uptime > 0: 
                    self.dt += self.step_size
                else :
                    self.dt = 0
                
                
                if self.dt > 10 * 60 and self.top_layer_Tank1 < self.T_hp_sp_h:
                     self.boiler_status = 'on'
                    
                
                if self.boiler_status == 'on':
                    if self.bottom_layer_Tank2 < self.T_hp_sp_h:
                        # self.boiler_demand = self.hwt_mass * 4184 * (self.T_hp_sp_h - self.bottom_layer_T_chp) / self.step_size
                        self.boiler_demand =  self.heat_demand             
                    elif self.boiler_uptime >= 15 * 60: #boiler uptime is in seconds
                        self.boiler_demand = 0
                        self.boiler_status = 'off'
                else:
                    
                    self.boiler_demand = 0
                
                logger_controller.debug(f'time : {time}\t Top layer temp : {self.top_layer_Tank2}, uptime : {self.chp_uptime}, chpstatus : {self.chp_status}, dt : {self.dt}, boiler : {self.boiler_status}, boiler uptime : {self.boiler_uptime}\n')
        
        # Control strategies for the operation of heat pump in cooling mode
        elif self.operation_mode.lower() == 'cooling':

            if (self.T_room > self.T_hp_sp_h) or ((self.bottom_layer_Tank0 - self.T_room) < 5):
                self.hp_status = 'on'

            if self.bottom_layer_Tank0 > 52:
                self.hp_status = 'off'

            if self.hp_status == 'on':
                if self.T_room > (self.T_hp_sp_l+0.5):
                    self.hp_demand = 10000000
                else:
                    self.hp_demand = 0
                    self.hp_status = 'off'
            else:
                self.hp_demand = 0

        # Setting the inlet temperature to the hot water tank from the heat pump, in the case where heat pump isn't
        # operational
        if self.hp_in_T is None:
            self.hp_in_T = self.hp_out_T
        
        if self.hp_supply is None:
            self.hp_supply = 0

        # Do the same as above for the CHP
        if self.chp_in_T is None:
            self.chp_in_T = self.chp_out_T
        
        if self.chp_supply is None:
            self.chp_supply = 0

        if self.boiler_supply is None:
            self.boiler_supply = 0
            
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
        self.tes0_heat_in_F = self.heat_in_F
        self.tes0_hp_out_F = self.hp_out_F
        self.tes1_hp_in_F = self.hp_in_F
        self.tes0_residual_flow = self.tes0_heat_in_F + self.tes0_hp_out_F

        #If Demand flow < hp flow, the residual flow from tank 0 to 1.
        if self.tes0_residual_flow > 0:
            self.tes1_hp_out_T = self.tes0_heat_out_T
            self.tes0_heat_out_F = - self.tes0_residual_flow
            self.tes1_hp_out_F = self.tes0_residual_flow

        else:
            self.tes0_heat_out_T = self.tes1_hp_out_T #Flow from 1 to 0.
            self.tes0_heat_out_F = - self.tes0_residual_flow
            self.tes1_hp_out_F = self.tes0_residual_flow

        if self.tes0_heat_in_F + self.tes0_heat_out_F + self.tes0_hp_out_F > 1e-5:
            raise ValueError("Tank-0 netflow error!")
        
        self.tes1_residual_flow = self.tes1_hp_in_F + self.tes1_hp_out_F

        if self.tes1_residual_flow > 0:
            self.tes2_hp_out_T = self.tes1_heat_out_T
            self.tes1_heat_out_F = - self.tes1_residual_flow
            self.tes2_hp_out_F = self.tes1_residual_flow

        else:
            self.tes1_heat_out_T = self.tes2_hp_out_T
            self.tes1_heat_out_F = self.tes1_residual_flow
            self.tes2_hp_out_F = - self.tes1_residual_flow

        if self.tes1_heat_out_F + self.tes1_hp_out_F + self.tes1_hp_in_F > 1e-5:
            raise ValueError("Tank-1 netflow error!")
        


    def calc_heat_supply(self):
        """Calculate the mass flows and temperatures of water, and the heat from the back up heater in the space
        heating (SH) circuit"""
        
        self.heat_dT = self.heat_out_T - self.heat_rT
        self.heat_in_F = self.heat_demand / (4184 * self.heat_dT)
        self.heat_supply = self.heat_in_F * 4184 * self.heat_dT
        if self.heat_out_T >= self.T_hr_sp:
            self.heat_in_T = self.heat_rT
            
            self.P_hr = 0
        else:
            self.P_hr = self.heat_in_F * 4184 * (self.T_hr_sp - self.heat_out_T)
            
            self.heat_in_T = self.heat_rT
        self.heat_out_F = - self.heat_in_F

    def calc_heat_supply(self):
        """Calculate the mass flows and temperatures of water, and the heat from the back up heater in the space
        heating (SH) circuit"""
        
        self.heat_dT = self.heat_out_T - self.heat_rT
        self.heat_in_F = self.heat_demand / (4184 * self.heat_dT)
        self.heat_supply = self.heat_in_F * 4184 * self.heat_dT
        
        if self.heat_out_T < self.T_hr_sp and self.hr_mode=='on':
            self.P_hr = self.heat_in_F * 4184 * (self.T_hr_sp - self.heat_out_T)

            self.heat_in_T = self.heat_rT

        else:
            self.heat_in_T = self.heat_rT

            self.P_hr = 0
        
        self.heat_out_F = - self.heat_in_F