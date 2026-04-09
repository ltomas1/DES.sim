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
    (`op_stages`), a list of heat output capacities (`heat_out_caps`), fluid
    properties (`cp`) and optional setpoints (`set_temp`, `set_flow`).

    Parameters
    - params (dict): configuration keys used by the transformer. Common keys:
        - 'heat_out_caps' (list or array): explicit heat output capacities (W)
        - 'nom_P_th' (float): nominal thermal power (W)
        - 'op_stages' (list): relative stage fractions (e.g. [0, 1])
        - 'cp' (float): specific heat capacity, default 4187 J/kgK
        - 'set_temp' (float): fixed outlet temperature (deg C)
        - 'set_flow' (float): fixed mass flow (kg/s)
        - 'efficiency' (float): nominal efficiency: fuel to thermal
        - 'heating_value' (float): fuel heating value (J/g or J/kg depending)
    """
    def __init__(self, params, *, warn: bool = True):
        

        self.validate_params(params, warn=warn)

        self.heat_out_caps = params.get('heat_out_caps', None)# list 
        self.nom_P_th = params.get('nom_P_th', None)
        self.op_stages = params.get('op_stages', [0,1])
        self.cp = params.get('cp', 4187) #specific heat capacity of the working fluid, default water J/kgK
        self.set_temp = params.get('set_temp', None)
        self.set_flow = params.get('set_flow', None) #fixed flow rate kg/s
        self.nom_eta = params.get('efficiency', None)
        self.heat_value = params.get('heating_value', 10833.3)


        # the inputs/outputs - decide whether a seperate class or not!
        
        self.P_th = None
        self.temp_in = None
        self.temp_out = None
        self.mdot_neg = None
        self.mdot = None
        self.fuel = None
        self.eta = self.nom_eta # Can be overwritten if startup behaviour is known.


        if self.heat_out_caps is None:
            if self.nom_P_th is not None:
                self.heat_out_caps = self.nom_P_th * np.asarray(self.op_stages)

        if self.nom_P_th is None:
            if self.heat_out_caps:
                self.nom_P_th = self.heat_out_caps[-1]

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
            
        else: # self.set_flow is not None
            self.mdot = self.set_flow
            if self.temp_in == None: #powershare case
                self.temp_out = None
            else:
                self.temp_out = ( self.P_th / (self.mdot * self.cp))  + self.temp_in


        self.calc_fuel()
        self.mdot_neg = -1 * self.mdot if self.mdot is not None else None #Powershare case

    def validate_params(self, params, *, warn: bool = True):
        """
        Base validation entrypoint:
        - Runs checks common to all Transformer_base subclasses
        - Delegates model-specific checks to _validate_model_params()
        """
        name = type(self).__name__
        hard_errors = []

        # Loop 1: warnings for defaults
        # default_warnings = {
        #     "heating_value": (
        #         "{name}: 'heating_value' not provided; Boiler will default to 10833.3."
        #     ),
        #     "cp": (
        #         "{name}: 'cp' (specific heat capacity) not provided; Boiler will default to 4187 J/kgK (water)."
        #     ),
        #     "op_stages": (
        #         "{name}: 'op_stages' not provided; Boiler will default to [0, 1] (0% and 100% of nominal power)."
        #     ),
        # }
        # for key, msg in default_warnings.items():
        #     if key not in params:
        #         tqdm.write(msg)

        # -------------------- warnings -------------------- 
        if warn:
            if params.get("heat_out_caps", None) is not None and (params.get("nom_P_th", None) is not None and params.get("op_stages", None)) is not None:
                tqdm.write(
                    f"- {name}: 'nom_P_th' and 'op_stages' are not required when 'heat_out_caps' is provided; using the provided 'heat_out_caps'."
                )
            if params.get("set_flow", None) is not None and params.get("set_temp", None) is not None:
                tqdm.write(
                    f"- {name}: Both 'set_flow' and 'set_temp' are provided; 'set_temp' will take precedence and 'set_flow' will be ignored."
                )
        # -------------------- constraints (dict rules, per-key) --------------------
        rules = {
            # required for these models
            "efficiency": {
                "required": True,
                "types": (int, float, np.number),
                "pred": lambda v: 0 < v <= 1,
                "msg": "'efficiency' must be a number in (0, 1].",
            },

            # optional common numeric params
            "nom_P_th": {
                "required": False,
                "types": (int, float, np.number),
                "pred": lambda v: v >= 0,
                "msg": "'nom_P_th' must be a number >= 0 when provided.",
            },
            "set_temp": {
                "required": False,
                "types": (int, float, np.number),
                "msg": "'set_temp' must be a number when provided.",
            },
            "set_flow": {
                "required": False,
                "types": (int, float, np.number),
                "msg": "'set_flow' must be a number when provided.",
            },
            "heating_value": {
                "required": False,
                "types": (int, float, np.number),
                "pred": lambda v: v > 0,
                "msg": "'heating_value' must be a number > 0 when provided.",
            },

            # lists
            "op_stages": {
                "required": False,
                "types": (list, tuple, np.ndarray),
                "pred": lambda v: (
                    len(v) > 0
                    and all(isinstance(x, (int, float, np.number)) and 0 <= x <= 1 for x in v)
                ),
                "msg": "'op_stages' must be a non-empty list/array of numbers in [0, 1].",
            },
            "heat_out_caps": {
                "required": False,
                "types": (list, tuple, np.ndarray),
                "pred": lambda v: (
                    len(v) > 0
                    and all(isinstance(x, (int, float, np.number)) and x >= 0 for x in v)
                ),
                "msg": "'heat_out_caps' must be a non-empty list/array of numbers >= 0.",
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
        if params.get("set_flow", None) is None and params.get("set_temp", None) is None:
            hard_errors.append(f"{name}: At least one of 'set_flow' or 'set_temp' must be defined.")

        if params.get("heat_out_caps", None) is None and params.get("nom_P_th", None) is None :
            hard_errors.append(f"{name}: Either 'heat_out_caps' or 'nom_P_th' and 'op_stages' must be defined.")

        # hook: boiler/chp add their own checks
        self._validate_model_params(params, hard_errors, warn=warn)

        if hard_errors:
            raise IncompleteConfigError(
                f"{name} configuration error(s):\n- " + "\n- ".join(hard_errors)
            )
        
        


    def _validate_model_params(self, params, hard_errors, *, warn: bool = True):
        """Hook for subclasses. Override in model classes."""
        pass


    def get_init_attrs(self):
        '''
        Simply returns a list of all user defined attributes in this class. 
        Useful to add to the attrs list in META.
        '''
        return list(vars(self).keys())


