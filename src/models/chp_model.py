# -*- coding: utf-8 -*-
"""
Created on Thu Jun  6 15:03:34 2024

@author: leroytomas
"""

class CHP_State():
    """Attributes that define the state of the CHP"""
    def __init__(self):
        self.Q_Demand = 0
        """The heat demand of the consumer in W"""

        self.eff_el = 0
        """The electrical efficieny of the CHP """

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
        self.chp_uptime = 0  #TODO why is this needed here, although, this data is not to be printed to csv, just outputed, how does chp_status work tho?


class CHPInputs():
    """Inputs variables to the CHP for each time step"""
    __slots__ = ['Q_Demand', 'eff_el', 'nom_P_th', 'mdot', 'step_size', 'temp_in', 'chp_status', 'fuel_eta', 'heat_value']

    def __init__(self, params):

        self.Q_Demand = None
        """The heat demand of the consumer in kW"""

        self.eff_el = params.get('eff_el')
        """The electrical efficieny of the CHP """

        self.nom_P_th = params.get('nom_P_th')
        """The nominal thermal power in W (in kW)"""

        self.mdot = params.get('mdot')
        """The mass flow rate of the water circuit in kg/s (in kg/h)"""
       
        self.step_size = None
        """step size in seconds"""
        
        self.temp_in = None
        """The input temperature coming from the water source (in °C)"""

        self.chp_status = 'off'

        self.fuel_eta = params.get('eta')
        """fuel efficiency of chp | Kwh_heat/kwh_fuel; from datasheet"""

        self.heat_value = params.get('hv')
        """Heating value of supplied natural gas, in wh/ standard cubic meter"""


        # self.temp_out = None
        # """The output temperature flowing out of the CHP (in °C)"""
        
class CHP:  # Defining the HeatPumpModel class
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
        self.lag_status = 'off'
        self.time_reset = 0
        self.uptime = 0
        
        self.temp_out = 0
        self.P_th = 0
        
        if 'cp' in  params.keys():
            self.cp = params.get('cp')
        else:
            self.cp = 4184

        self.startup_coeff = params.get('startup_coeff')
        
        self.inputs = CHPInputs(params)
        """stores the input parameters of the heat pump model in a
        :class:`.CHPModel.CHPInputs` object"""
        self.state = CHP_State()
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
        
        reglimit = 11 # the regression model works only for the first 11 minutes.
        if self.inputs.chp_status == 'off' or self.inputs.chp_status == None:
            self.P_th = 0
            self.uptime = 0
            # self.temp_out = self.inputs.temp_in
        else :
          
            if self.inputs.chp_status != self.lag_status: #lag_status initialized to off, so when turned on, reset var assigned
                self.time_reset = time
            #to count time passed after each startup. In the previous line, time_reset is assigned the time of initialisation of startup.
            self.uptime = (time - self.time_reset)/60  #the regression model takes time in minutes.
            
            if self.uptime < (reglimit):
                self.P_th = 0
                for i in range(len(self.startup_coeff)):
                    self.P_th += self.startup_coeff[i] * self.uptime**i #i starts for 0, so will work for intercept as well.
                
                # self.P_th = -15.7 + 9.6 * self.time  #linear regression model fitted on startup data for the first 10 minutes.
                
                self.P_th = self.P_th * 1000 # converting to watts
                if self.P_th < 0:  #for the lack of a better model :)
                    self.P_th = 0

            else:
                self.P_th = self.inputs.nom_P_th

            # If the time step is greater than the regression limit, then the first o/p value will be < nom_Pth, cuz ramp up.
            if step_size/60 > reglimit and self.uptime == 0:
                self.P_th = (5999.667 + self.inputs.nom_P_th*((step_size/60) - 11)/60)/(step_size/3600) #(wh + w * h)/stepsize in h = W
                # 5999.667 Wh, obtained from measured data, energy in the first 11 minutes.

                
        
        self.calc_P_el()
        self.temp_out = ( self.P_th * self.inputs.step_size  / (self.inputs.mdot *self.inputs.step_size * self.cp))  + self.inputs.temp_in
        
        self.lag_status = self.inputs.chp_status  #the current status variable from controller, to be compared in the next iteration.

        # Fuel consumption
        
        # self.fuel_eta = 0.083 # From measured data
        # self.fuel_l = self.P_th*(self.inputs.step_size/3600) * self.fuel_eta
        self.fuel_m3 = (self.P_th*(self.inputs.step_size/3600))/(self.inputs.fuel_eta * self.inputs.heat_value)

        # Update the state of the CHP for the outputs
        self.state.Q_Demand = self.inputs.Q_Demand
        self.state.eff_el = self.inputs.eff_el
        self.state.mdot = self.inputs.mdot
        self.state.mdot_neg = - self.inputs.mdot
        self.state.nom_P_th = self.inputs.nom_P_th
        self.state.P_th = self.P_th
        self.state.temp_in = self.inputs.temp_in
        self.state.temp_out = self.temp_out
        self.state.P_el = self.P_el

        self.state.fuel_m3 = self.fuel_m3
        self.state.chp_uptime = self.uptime
        
    def calc_P_el(self):
        
        self.P_el = self.P_th * self.inputs.eff_el
        
    def print_instance_attributes(self):
        for attribute, value in self.__dict__.items():
            print(attribute, '=', value)

        

        
        