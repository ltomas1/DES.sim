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


class CHPInputs():
    """Inputs variables to the CHP for each time step"""
    __slots__ = ['Q_Demand', 'eff_el', 'nom_P_th', 'mdot', 'step_size', 'temp_in']

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
            'mdot': 200, # in kg/h
            }
        
    """

    def __init__(self, params):  # Initializing the class
        """
        Initializes the simpe CHP Model 
        
        """
        
        self.temp_out = 0
        self.P_th = 0
        
        if 'cp' in  params.keys():
            self.cp = params.get('cp')
        else:
            self.cp = 4184
        
        self.inputs = CHPInputs(params)
        """stores the input parameters of the heat pump model in a
        :class:`.CHPModel.CHPInputs` object"""
        self.state = CHP_State()
        """stores the state variables of the CHP in a
        :class:`.CHPModel.CHP_State` object"""
                
    def step(self, time):  # Defining the step method
        """
        simulates the CHP for one timestep
        """
        self.time = time/60
        
        if self.inputs.Q_Demand == 0:
            self.P_th = 0
            # self.temp_out = self.inputs.temp_in
        elif self.time < (11*60):
            self.P_th = -15.7 + 9.6 * self.time  #linear regression model fitted on startup data for the first 10 minutes.
            if self.P_th < 0:  #for the lack of a better linear model :)
                self.P_th = 0
        else:
            self.P_th = self.inputs.nom_P_th
        
        self.calc_P_el()
        self.temp_out = ( self.P_th * self.inputs.step_size  / (self.inputs.mdot *self.inputs.step_size * self.cp))  + self.inputs.temp_in
        
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
        
    def calc_P_el(self):
        
        self.P_el = self.P_th / self.inputs.eff_el
        
    def print_instance_attributes(self):
        for attribute, value in self.__dict__.items():
            print(attribute, '=', value)

        

        
        