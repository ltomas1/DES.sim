'''
A common class for all energy transformer


In the current iteration, startup behaviour can be modelled with coefficients only if one power stage(e.g CHP).
@author : AqibThennadan
'''
#TODO what if primarily electrical energy transformer, heat is byproduct?
#TODO time in secods, uptime, reg coefficients...

#TODO unittests
#TODO could add models to seperate lists based on prefix, to keep unique entity IDs, else boiler and chp would be in the same list, with increase ID no.


import mosaik_api
from tqdm import tqdm
import numpy as np
import warnings

class IncompleteConfigError(Exception) : pass
class OverdefinedConfig(UserWarning) : pass

class Transformer_base():
    def __init__(self, params):

        self.heat_out_caps = params.get('heat_out', None)# list
        self.nom_P_th = params.get('nom_P_th', None)
        self.op_stages = params.get('op_stages', [0,1])
        self.cp = params.get('cp', 4187)
        self.set_temp = params.get('set_temp', None)
        self.set_flow = params.get('set_flow', None)
        self.nom_eta = params.get('efficiency', None)
        self.heat_value = params.get('heating_value', 10833.3)
        self.step_size = params.get('step_size')

        # the inputs/outputs - decide whether a seperate class or not!
        self.status = None
        self.P_th = None
        self.P_el = None
        self.uptime = 0
        self.lag_status = 'off'
        self.time_reset = 0
        self.temp_in = None
        self.temp_out = None
        self.Q_demand = None
        self.mdot_neg = None
        self.mdot = None
        self.fuel = None
        self.eta = self.nom_eta # Can be overwritten if startup behaviour is known.


        if not self.heat_out_caps :
            self.heat_out_caps = self.nom_P_th * np.asarray(self.op_stages)
        if self.heat_out_caps and self.nom_P_th and self.op_stages:
            warnings.warn("nom_P_th and op_stages not required if heat_out_caps defined. Defaulting to the provided heat_out_caps", OverdefinedConfig)
        if self.nom_P_th is None:
            if self.heat_out_caps:
                self.nom_P_th = self.heat_out_caps[-1]
            else :
                raise IncompleteConfigError("Either heat_out_caps or nom_P_th has to be defined.")

    def calc_fuel(self):
        if self.eta:
            self.fuel = (self.P_th*(self.step_size/3600))/(self.eta * self.heat_value)
    
    def step(self, time):


        if self.status == 'off' or self.status is None :
            self.P_th = 0
            self.uptime = 0
            
        else :
          
            if self.status != self.lag_status: #lag_status initialized to off, so when turned on, reset var assigned
                self.time_reset = time
            #to count time passed after each startup. In the previous line, time_reset is assigned the time of initialisation of startup.
            self.uptime = (time - self.time_reset)/60  #the regression model takes time in minutes.
            
            
            self.P_th = min((i for i in self.heat_out_caps if i >= self.Q_demand), default=self.heat_out_caps[-1])       
        
        # IDEA : Could have the following logic as a base Transformer class; child classes of this class could add functionality like startup and electricity.
        if self.set_temp:
            self.temp_out = self.set_temp
            self.mdot = self.P_th/(self.cp * (self.temp_out - self.temp_in))
            self.mdot = max(0, self.mdot) #To prevent reverse flow!
            # tqdm.write(f'BOiler mass flow : {self.mdot}, temp_in : {self.temp_in}; temp_out : {self.temp_out}, demand : {self.Q_demand}, uptime : {self.uptime}')
            
        elif self.set_flow:
            self.mdot = self.set_flow
            
            self.temp_out = ( self.P_th / (self.mdot * self.cp))  + self.temp_in

        else :
            raise IncompleteConfigError("Atleast one 'set_flow' or 'set_temp' needs to be defined!")

        self.calc_fuel()
        self.mdot_neg = -1 * self.mdot

        self.lag_status = self.status

    def get_init_attrs(self):
        '''
        Simply returns a list of all user defined attributes in this class. 
        Useful to add to the attrs list in META.
        '''
        return list(vars(self).keys())


