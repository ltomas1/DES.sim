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

        self.T_hp_sp_winter = params.get('T_hp_sp_winter')
        self.T_hp_sp_surplus = params.get('T_hp_sp_surplus')
        self.T_hr_sp_hwt = params.get('T_hr_sp_hwt', None)
        # self.T_hr_sp_chp = params.get('T_hr_sp_chp', None)
        self.T_dhw_sp = params.get('T_dhw_sp', None)
        # self.heat_dT = params.get('heat_dT', 7)
        self.heat_rT = params.get('heat_rT', 20)
        self.operation_mode = params.get('operation_mode', 'heating')
        self.control_strategy = params.get('control_strategy', '1')
        self.hr_mode = params.get('hr_mode', 'off').lower()
        self.T_chp_h = params.get('T_chp_h')

        self.config = params.get('supply_config')
        self.sh_out = params.get('sh_out')  #Tank which serves as the Output connection for space heating
        self.dhw_out = params.get('dhw_out')##Tank which serves as the Output connection for hot water demand

        self.stepsize = params.get('step_size')
        self.boiler_mode = params.get('boiler_mode').lower()
        self.params_hwt = params.get('params_hwt')

        self.T_amb = None                   # The ambient air temperature (in °C)
        self.heat_source_T = None           # The temperature of source for the heat pump (in °C)
        self.T_room = None                  # The temperature of the room (used in cooling mode, in °C)

        self.heat_demand = None             # The total heat demand from SH & DHW (in W)
        self.dhw_demand = None
        self.sh_demand = None

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

        self.max_flow = None            #The max flow rate permissible in one step.
        self.P_hr = [0,0,0]             # Power demand from heating rods of the respective tanks. #TODO more robust for flexible number of tanks

        #TODO write all comments for TES variables 
        self.tes0_heat_out_T = None         # The temperature of the heat_out connection for the tank 0 
        self.tes0_heat_out_F = None         
        self.tes0_heat_in_F = None
        self.tes0_hp_out_F = None
        self.tes0_heat_in2_F = None
        self.tes0_heat_in2_T = None
        self.tes0_heat_in_T = None
        self.tes0_heat_out2_F = None
        self.tes0_heat_out2_T = None

        self.tes1_heat_out_T = None
        self.tes1_heat_out_F = None
        self.tes1_hp_in_F = None
        self.tes1_hp_out_T = None
        self.tes1_hp_out_F = None
        self.tes1_heat_out2_F = 0
        self.tes1_heat_out2_T = None
        self.tes1_heat_in2_F = None
        self.tes1_heat_in2_T = None
        

        self.tes2_heat_out_F = None
        self.tes2_heat_out_T = None
        self.tes2_hp_out_T = None
        self.tes2_hp_out_F = None
        self.tes2_heat_out2_F = None
        self.tes2_heat_out2_T = None
        self.tes2_heat_in2_F = None
        self.tes2_heat_in2_T = None

        self.hwt2_hr_1 = 0

        


    def step(self, time):
        """Perform simulation step with step size step_size"""

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

        if self.tes0_heat_in_F is None :
            self.tes0_heat_in_F = 0
        if self.tes0_hp_out_F is None :
            self.tes0_hp_out_F = 0
        

        # Calculate the mass flows, temperatures and heat from back up heater for the SH circuit
        self.calc_heat_supply(self.config)

        # Calculate the heat supply of the heating rods
        # self.tankLayer_volume = 3.14 * self.params_hwt['height'] * (self.params_hwt['diameter']/2e3)**2  #height is in mm, so H/10^3 * density 1000kg/m3; so density omitted here!
        self.tankLayer_mass = self.params_hwt['volume'] * 1 / self.params_hwt['n_layers'] #1L = 1Kg
        
        # if chaning hr position, change the temp value here as well!
        if self.params_hwt['heating_rods']['hr_1']['mode'] == 'on' and self.top_layer_Tank2 < self.params_hwt['heating_rods']['hr_1']['T_max']:
            self.hwt2_hr_1 = self.tankLayer_mass * 4184 * (self.params_hwt['heating_rods']['hr_1']['T_max'] - self.top_layer_Tank2)

        self.hwt1_hr_1, self.hwt0_hr_1 = 0,0 

        # Control strategies for the operation of heat pump in heating mode
        if self.operation_mode.lower() == 'heating':
            #Datasheet logic control
            if self.control_strategy == '1':
                                
                if self.bottom_layer_Tank0 < self.T_hp_sp_surplus: #Turns on only when below threshold of 35 degrees.
                    
                    self.hp_status = 'on'
                    
                if self.hp_status == 'on': # Hp runs until upper threshold achieved.
                    if self.bottom_layer_Tank0 < self.T_hp_sp_winter:
                        self.hp_demand = self.hwt_mass * 4184 * (self.T_hp_sp_winter - self.bottom_layer_Tank0) / self.step_size
                    else:
                        self.hp_demand = 0
                        self.hp_status = 'off'
                else:
                    self.hp_demand = 0

                if self.hp_status == None:
                    self.hp_status = 'off'
                    
                if self.top_layer_Tank2 < self.T_dhw_sp: #i.e high heat demand
                    self.chp_status = 'on'
                    
                
                if self.chp_status == 'on': #runs until bottom layer of tank 2 reaches the threshold
                    if self.bottom_layer_Tank2 < self.T_chp_h:
                        self.chp_demand = self.hwt_mass * 4184 * (self.T_dhw_sp - self.bottom_layer_Tank2) / self.step_size
                    elif self.chp_uptime >= 15: #15 minute minimum runtime
                        self.chp_demand = 0
                        self.chp_status = 'off'
                    else:
                        self.chp_demand = self.hwt_mass * 4184 * (self.T_dhw_sp - self.bottom_layer_Tank2) / self.step_size

                    # logger_controller.debug(f'time : {time} \tbottom layer : {self.bottom_layer_T_chp}, uptime : {self.chp_uptime}, status : {self.chp_status}')
                else:
                    
                    self.chp_demand = 0
                
                #If the CHP is not able to keep up :
                # Data transfer only at end of step, so this ensures, dt incremented after one step of chp.
                if self.top_layer_Tank2 < self.T_dhw_sp and self.chp_uptime > 0: 
                    self.dt += self.step_size
                else :
                    self.dt = 0
                
                #! what does this mean? why are we looking at the tank1 top temp?
                if self.dt > 10 * 60 and self.top_layer_Tank2 < self.T_dhw_sp and self.boiler_mode == 'on':
                     self.boiler_status = 'on'
                    
                
                if self.boiler_status == 'on':
                    if self.bottom_layer_Tank2 < self.T_chp_h:
                        self.boiler_demand = self.hwt_mass * 4184 * (self.T_dhw_sp - self.bottom_layer_Tank2) / (self.step_size * 2) # heat up the entire tank to T_hr_sp in 2 time steps
                        # self.boiler_demand =  self.heat_demand             
                    elif self.boiler_uptime >= 15 * 60: #boiler uptime is in seconds
                        self.boiler_demand = 0
                        self.boiler_status = 'off'
                    else :
                        self.boiler_demand =  self.heat_demand
                else:
                    
                    self.boiler_demand = 0
                
                # logger_controller.debug(f'time : {time}\t Top layer temp : {self.top_layer_Tank2}, uptime : {self.chp_uptime}, chpstatus : {self.chp_status}, dt : {self.dt}, boiler : {self.boiler_status}, boiler uptime : {self.boiler_uptime}\n')
        
        # Control strategies for the operation of heat pump in cooling mode
        elif self.operation_mode.lower() == 'cooling':

            if (self.T_room > self.T_hp_sp_winter) or ((self.bottom_layer_Tank0 - self.T_room) < 5):
                self.hp_status = 'on'

            if self.bottom_layer_Tank0 > 52:
                self.hp_status = 'off'

            if self.hp_status == 'on':
                if self.T_room > (self.T_hp_sp_surplus+0.5):
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
        # self.tes0_heat_in_F = self.heat_in_F
        self.tes0_hp_out_F = self.hp_out_F
        self.tes1_hp_in_F = self.hp_in_F
        self.tes0_residual_flow = self.tes0_heat_in_F + self.tes0_hp_out_F + self.tes0_heat_out2_F

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
        
        self.tes1_residual_flow = self.tes1_hp_in_F + self.tes1_hp_out_F + self.tes1_heat_out2_F
        # logger_controller.debug(f'tes1 residual flow: {self.tes1_residual_flow}')

        if self.tes1_residual_flow > 0:
            self.tes2_hp_out_T = self.tes1_heat_out_T
            self.tes1_heat_out_F = - self.tes1_residual_flow
            self.tes2_hp_out_F = self.tes1_residual_flow

        else:
            self.tes1_heat_out_T = self.tes2_hp_out_T
            self.tes1_heat_out_F = - self.tes1_residual_flow
            self.tes2_hp_out_F =  self.tes1_residual_flow

        if self.tes1_heat_out_F + self.tes1_hp_out_F + self.tes1_hp_in_F + self.tes1_heat_out2_F > 1e-5:
            raise ValueError("Tank-1 netflow error!")
        
        # logger_controller.debug(f'TES0:  heat_out:{self.tes0_heat_out_F}, heat_in:{self.tes0_heat_in_F}, hp_out:{self.tes0_hp_out_F}, resid : {self.tes0_residual_flow}\n')

    # def calc_heat_supply(self):
    #     """Calculate the mass flows and temperatures of water, and the heat from the back up heater in the space
    #     heating (SH) circuit"""
        
    #     self.heat_dT = self.heat_out_T - self.heat_rT
    #     self.heat_in_F = self.heat_demand / (4184 * self.heat_dT)
    #     self.heat_supply = self.heat_in_F * 4184 * self.heat_dT
    #     if self.heat_out_T >= self.T_hr_sp:
    #         self.heat_in_T = self.heat_rT
            
    #         self.P_hr = 0
    #     else:
    #         self.P_hr = self.heat_in_F * 4184 * (self.T_hr_sp - self.heat_out_T)
            
    #         self.heat_in_T = self.heat_rT
    #     self.heat_out_F = - self.heat_in_F


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
        
        if out_temp < self.T_dhw_sp and self.hr_mode == 'on':
            
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
    
    def calc_heat_supply(self, config):
        """Calculate the mass flows and temperatures of water, and the heat from the back up heater in the space
        heating (SH) circuit"""
        

        #Capping the mass flow rate
        self.max_flow = 20
        
        #attributes to be updated if Heating rod turned on.
        updates = [self.P_hr[2], self.tes2_heat_out_T, self.tes0_heat_in_F, self.heat_supply]
        outputkeys = ['P', 'out_temp', 'flow', 'supply'] #output keys of the heating rod return dict.
        
        if config == '2-runner':

            self.heat_dT = self.tes2_heat_out_T - self.heat_rT
            try:
                self.tes0_heat_in_F = self.heat_demand/ (4184 * self.heat_dT)
            except ZeroDivisionError:
                self.tes0_heat_in_F = 0

            self.tes0_heat_in_F = max(0,self.tes0_heat_in_F)
            self.heat_supply = self.tes0_heat_in_F * 4184 * self.heat_dT

            self.tes0_heat_in_T = self.heat_rT

            results = self.calc_hr_P(self.tes2_heat_out_T, self.heat_demand)
            #If heating rods turns on, flow, temp and supply overwritten, else not
            for i, j in enumerate(outputkeys):
                updates[i] = results.get(j, updates[i])

            self.tes2_heat_out_F = -self.tes0_heat_in_F
            
            self.dhw_supply, self.sh_supply = 0,0
        
        
        
        
        if config == '3-runner':
            
            sh_out = 'tes'+self.sh_out+'_heat_out2'  #self.sh_out = 1 or 2, passed as a parameter to controller.
            dhw_out = 'tes'+self.dhw_out+'_heat_out'            
            self.sh_out_T = getattr(self, sh_out+'_T')
            self.dhw_out_T = getattr(self,dhw_out+'_T')

            self.heat_dT_sh = self.sh_out_T - self.heat_rT
            self.heat_dT_dhw = self.dhw_out_T - self.heat_rT
            
            try:
                sh_F = self.sh_demand/ (4184 * self.heat_dT_sh)
            except ZeroDivisionError:
                sh_F = 0
            try:
                dhw_F = self.dhw_demand/(4184 * self.heat_dT_dhw)
            except ZeroDivisionError:
                dhw_F = 0
            
            
            sh_F = max(0,sh_F)  #-ve flow set to zero.
            dhw_F = max(0,dhw_F)
            sh_F = min(self.max_flow, sh_F)
            dhw_F = min(self.max_flow, dhw_F)         
            

            self.sh_supply = sh_F * 4184 * self.heat_dT_sh
            self.dhw_supply = dhw_F * 4184 * self.heat_dT_dhw
            self.heat_supply = 0 #for now, this will be exclusive to 2-runner model. To make it easier in visu.ipynb(sankey)
            
            #If the heating rod is on, the flow rate, temperature and supplied energy is overwritten, else not
            # results_sh = self.calc_hr_P(sh_out_T, self.sh_demand)
            results_dhw = self.calc_hr_P(self.dhw_out_T, self.dhw_demand)
            
            updates_sh = [self.P_hr[int(self.sh_out)], self.sh_out_T, sh_F, self.sh_supply]
            updates_dhw = [self.P_hr[int(self.dhw_out)], self.dhw_out_T, dhw_F, self.dhw_supply]
            
            #If heating rods turns on, flow, temp and supply overwritten, else not
            # for i, j in enumerate(outputkeys):
            #     updates_sh[i] = results_sh.get(j, updates_sh[i])

            for i, j in enumerate(outputkeys):
                updates_dhw[i] = results_dhw.get(j, updates_dhw[i])

            self.P_hr[int(self.dhw_out)], self.dhw_out_T, dhw_F, self.dhw_supply = updates_dhw
            
            self.tes0_heat_in_F = sh_F + dhw_F
            self.tes0_heat_in_T = self.heat_rT

            setattr(self,sh_out+'_F', -sh_F)
            setattr(self,dhw_out+'_F', -dhw_F)

            setattr(self, sh_out+'_T', self.sh_out_T)
            setattr(self, dhw_out+'_T', self.dhw_out_T)