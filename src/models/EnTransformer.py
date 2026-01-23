"""
Module providing a basic energy transformer model used across the project.

This module defines a small, generic `Transformer_base` class that implements
simple first-principle thermodynamics to compute mass flow, outlet
temperature and fuel consumption from an input temperature and a requested
thermal power. The model is intentionally lightweight and intended for use in
co-simulation scenarios or as a building block for more detailed models.

Units and conventions used in the class:
- Temperature: degrees Celsius (or consistent temperature units)
- Power: Watts (W)
- Mass flow: kilograms per second (kg/s)
- Specific heat capacity `cp`: J/(kg*K)
- `step_size` (expected on the instance): seconds (s)

Author: AqibThennadan
"""
#TODO what if primarily electrical energy transformer, heat is byproduct?
#TODO time in secods, uptime, reg coefficients...

#TODO unittests
#TODO could add models to seperate lists based on prefix, to keep unique entity IDs, else boiler and chp would be in the same list, with increase ID no.


import mosaik_api
from tqdm import tqdm
import numpy as np
import warnings
import numpy as np
import warnings

class IncompleteConfigError(Exception):
    """Raised when required configuration for a transformer is missing."""


class OverdefinedConfig(UserWarning):
    """Warning raised when configuration contains redundant definitions.

    For example, if both `heat_out_caps` and `nom_P_th` with `op_stages` are
    provided, the class will prefer `heat_out_caps` and issue this warning.
    """

class Transformer_base:
    """Generic energy transformer implementing basic thermal balance.

    The class accepts a dictionary of `params` describing capabilities such as
    nominal thermal power (`nom_P_th`), discrete operation stages
    (`op_stages`), a list of heat output capacities (`heat_out`), fluid
    properties (`cp`) and optional setpoints (`set_temp`, `set_flow`).

    Parameters
    - params (dict): configuration keys used by the transformer. Common keys:
        - 'heat_out' (list or array): explicit heat output capacities (W)
        - 'nom_P_th' (float): nominal thermal power (W)
        - 'op_stages' (list): relative stage fractions (e.g. [0, 1])
        - 'cp' (float): specific heat capacity, default 4187 J/kgK
        - 'set_temp' (float): fixed outlet temperature (deg C)
        - 'set_flow' (float): fixed mass flow (kg/s)
        - 'efficiency' (float): nominal efficiency: fuel to thermal
        - 'heating_value' (float): fuel heating value (J/g or J/kg depending)
    """
    def __init__(self, params):

        self.heat_out_caps = params.get('heat_out', None)# list
        self.nom_P_th = params.get('nom_P_th', None)
        self.op_stages = params.get('op_stages', [0,1])
        self.heat_out_caps = params.get('heat_out', None)# list
        self.cp = params.get('cp', 4187) #specific heat capacity of the working fluid, default water J/kgK
        self.set_temp = params.get('set_temp', None)
        self.set_flow = params.get('set_flow', None) #fixed flow rate kg/s
        self.nom_eta = params.get('efficiency', None)
        self.heat_value = params.get('heating_value', 10833.3)
        self.step_size = None


        # the inputs/outputs - decide whether a seperate class or not!
        
        self.P_th = None
        self.temp_in = None
        self.temp_out = None
        self.mdot_neg = None
        self.mdot = None
        self.fuel = None
        self.eta = self.nom_eta # Can be overwritten if startup behaviour is known.


        if not self.heat_out_caps :
            self.heat_out_caps = self.nom_P_th * np.asarray(self.op_stages)
        if self.heat_out_caps is not None and self.nom_P_th is not None and self.op_stages is not None:
            warnings.warn("nom_P_th and op_stages not required if heat_out_caps defined. Defaulting to the provided heat_out_caps", OverdefinedConfig)
        if self.nom_P_th is None:
            if self.heat_out_caps:
                self.nom_P_th = self.heat_out_caps[-1]
            else :
                raise IncompleteConfigError("Either heat_out_caps or nom_P_th has to be defined.")

    def calc_fuel(self):
        """Calculate fuel consumption for the last time step.

        The computation uses the current thermal power output `P_th`, the
        instance's `eta` (efficiency), the configured `heat_value` and the
        model's `step_size` (which must be set on the instance prior to
        calling). The resulting `fuel` is stored on the instance. Units are
        consistent with the configured `heat_value` and `step_size`.
        """

        if self.eta:
            self.fuel = (self.P_th * (self.step_size / 3600)) / (
                self.eta * self.heat_value
            )
    
    def step(self, time):      
        """Advance the transformer's state for one simulation step.

        This method uses the currently configured `P_th`, `temp_in` and
        either `set_temp` or `set_flow` to compute `mdot` (mass flow) and
        `temp_out` (outlet temperature). It then updates derived quantities
        such as `fuel` and `mdot_neg`.

        Parameters
        - time: current simulation time (unused in the basic model but kept
          for compatibility with external simulators).

        Behaviour
        - If `set_temp` is provided, `temp_out` is fixed and `mdot` is
          computed from the requested thermal power and temperature rise.
        - If `set_flow` is provided, `mdot` is fixed and `temp_out` is
          computed from the requested thermal power and mass flow.
        - If neither `set_temp` nor `set_flow` is configured an
          `IncompleteConfigError` is raised.
        """

        if self.set_temp:
            self.temp_out = self.set_temp
            if self.temp_in == None: #Powershare case
                self.mdot = None
            else:
                self.mdot = self.P_th/(self.cp * (self.temp_out - self.temp_in))
                self.mdot = max(0, self.mdot) #To prevent reverse flow!
            # tqdm.write(f'BOiler mass flow : {self.mdot}, temp_in : {self.temp_in}; temp_out : {self.temp_out}, demand : {self.Q_demand}, uptime : {self.uptime}')
            
        elif self.set_flow:
            self.mdot = self.set_flow
            if self.temp_in == None: #powershare case
                self.temp_out = None
            else:
                self.temp_out = ( self.P_th / (self.mdot * self.cp))  + self.temp_in

        else :
            raise IncompleteConfigError("Atleast one 'set_flow' or 'set_temp' needs to be defined!")

        self.calc_fuel()
        self.mdot_neg = -1 * self.mdot if self.mdot is not None else None #Powershare case

    def get_init_attrs(self):
        '''
        Simply returns a list of all user defined attributes in this class. 
        Useful to add to the attrs list in META.
        '''
        return list(vars(self).keys())


