# -*- coding: utf-8 -*-


#Logging setup------------------------------------------------------------------------------------------------------------#
import logging

logger_boiler = logging.getLogger("mosaik_logger")
logger_boiler.setLevel(logging.DEBUG)  # Log everything (DEBUG, INFO, WARNING, ERROR)

# Create a file handler to store logs
file_handler_boiler = logging.FileHandler("boiler_mosaik_simulation.log")  # Save to file
file_handler_boiler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

logger_boiler.addHandler(file_handler_boiler)
#----------------------------------------------------------------------------------------------------------------------------#

class Boiler_State():
    """Attributes that define the state of the CHP"""
    def __init__(self):
        self.Q_Demand = 0
        """The heat demand of the consumer in W"""

        self.nom_P_th = 0
        """The nominal thermal power in W"""

        self.mdot = 0
        """The mass flow rate of the water circuit in kg/s """
        
        self.mdot_neg = 0
        """The negative mass flow rate of the water circuit in kg/s"""
        
        self.temp_out = 0
        """The output temperature flowing out of the CHP (in °C)"""
        
        self.P_th = 0
        """ The actual thermal power output of the CHP in W"""

        self.fuel_m3 = 0
        """ Fuel consumption in stand cubic meter"""

        self.boiler_uptime = 0


class BoilerInputs():
    """Inputs variables to the CHP for each time step"""
    __slots__ = ['Q_Demand', 'nom_P_th', 'mdot', 'step_size', 'temp_in', 'fuel_eta', 'heat_value', 'boiler_status']

    def __init__(self, params):

        self.Q_Demand = None
        """The heat demand of the consumer in kW"""

        self.nom_P_th = params.get('nom_P_th')
        """The nominal thermal power in W (in kW)"""

        self.mdot = params.get('mdot')
        """The mass flow rate of the water circuit in kg/s (in kg/h)"""
       
        self.step_size = None
        """step size in seconds"""
        
        self.temp_in = None
        """The input temperature coming from the water source (in °C)"""

        self.boiler_status = 'off'

        self.fuel_eta = params.get('eta')
        """fuel efficiency of chp | Kwh_heat/kwh_fuel; from datasheet"""

        self.heat_value = params.get('hv')
        """Heating value of supplied natural gas, in wh/ standard cubic meter"""



        # self.temp_out = None
        # """The output temperature flowing out of the CHP (in °C)"""
        
class GasBoiler:  # Defining the HeatPumpModel class
    """
    CHP model based on an energy balance calculation with a given efficiency
    
    CHP parameters are provided at instantiation by the dictionary **params**. This is an example, how
    the dictionary might look like::

        params = {
            'eff_el': 0.8,
            'nom_P_th': 20,      
            'mdot': 200, # in kg/h,
            'startup_coeff : [] 
            }
        
    """

    def __init__(self, params):  # Initializing the class
        """
        Initializes the simpe CHP Model 
        
        """
        
        self.temp_out = 0
        self.P_th = 0
        self.lag_status = 'off'
        self.uptime = 0
        self.time_reset = 0

        if 'cp' in  params.keys():
            self.cp = params.get('cp')
        else:
            self.cp = 4184
        
        self.inputs = BoilerInputs(params)
        """stores the input parameters of the heat pump model in a
        :class:`.CHPModel.CHPInputs` object"""
        self.state = Boiler_State()
        """stores the state variables of the CHP in a
        :class:`.CHPModel.CHP_State` object"""
                
    
    def step(self, time, step_size):  # Defining the step method
        """
        simulates the CHP for one timestep
               
        """
        """_summary_

        Args:
            time (int): time returned by the mosaik sim, in seconds
            step_size (int): simulation step size, in seconds
        """
        
        if self.inputs.boiler_status != self.lag_status: #lag_status initialized to off, so when turned on, reset var assigned
            self.time_reset = time
            #to count time passed after each startup. In the previous line, time_reset is assigned the time of initialisation of startup.
        self.uptime = (time - self.time_reset)
        
        
        if self.inputs.Q_Demand == 0 or self.inputs.Q_Demand == None:
            self.P_th = 0

            self.inputs.mdot = 0
            # self.temp_out = self.inputs.temp_in
        else :

            self.P_th = min((i for i in self.inputs.nom_P_th if i >= self.inputs.Q_Demand), default=370000)

        self.lag_status = self.inputs.boiler_status
       
                
        # self.temp_out = ( self.P_th / (self.inputs.mdot * self.cp))  + self.inputs.temp_in
        # Trying out variable volume rate

        self.temp_out = 75
        self.inputs.mdot = self.P_th/((self.temp_out - self.inputs.temp_in) * self.cp)
        if self.inputs.mdot < 0:
            logger_boiler.debug(f"Boiler \t: Flow : {self.inputs.mdot}, tempin : {self.inputs.temp_in}, Pth : {self.P_th}")
            self.inputs.mdot = 0
        


        # Fuel consumption
        
        # self.fuel_eta = 0.083 # From measured data
        # self.fuel_l = self.P_th*(self.inputs.step_size/3600) * self.fuel_eta
        self.fuel_m3 = (self.P_th*(self.inputs.step_size/3600))/(self.inputs.fuel_eta * self.inputs.heat_value)

        # Update the state of the CHP for the outputs
        self.state.Q_Demand = self.inputs.Q_Demand
        self.state.mdot = self.inputs.mdot
        self.state.mdot_neg = - self.inputs.mdot
        self.state.nom_P_th = self.inputs.nom_P_th
        self.state.P_th = self.P_th
        self.state.temp_in = self.inputs.temp_in
        self.state.temp_out = self.temp_out

        self.state.fuel_m3 = self.fuel_m3
        self.state.boiler_uptime = self.uptime
        
    def print_instance_attributes(self):
        for attribute, value in self.__dict__.items():
            print(attribute, '=', value)

        