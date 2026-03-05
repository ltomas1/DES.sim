"""
Module for simulating a gas boiler using basic thermal balance principles.
The module inherits basic functionality from the Transformer_base class in
the EnTransformer module.

Author: AqibThennadan
"""

import mosaik_api

from models.EnTransformer import Transformer_base
import numpy as np
from tqdm import tqdm

class Gboiler(Transformer_base):
    """Gas boiler model (Gboiler) extending Transformer_base.
    This class models a staged gas boiler with optional startup transients for
    power output and efficiency. It determines an appropriate thermal power
    stage from available heat_out_caps based on the current heat demand, models
    reduced output and efficiency during startup using polynomial regressions,
    and delegates hydraulic/thermal calculations to Transformer_base.step().
    Parameters
    ----------
    params : dict
        Configuration dictionary. Recognized keys:
        - 'startup_coeff' (list[float] | None): Coefficients of a polynomial
          (a0, a1, a2, ...) giving instantaneous thermal power (in kW) as a
          function of uptime (minutes) during startup. The polynomial is
          evaluated at uptime (minutes), then converted to W (multiplied by 1000).
        - 'startup_limit' (float | None): Startup duration (minutes). Used to
          determine when the startup transient ends.
        - 'startup_eta_coeff' (list[float] | None): Coefficients of a polynomial
          (a0, a1, ...) giving thermal efficiency as a function of uptime
          (minutes) during startup.
        - step_size (float | None): Time-step size in seconds (used when scaling
          averaged startup energy/efficiency across a timestep). May also be
          provided/managed by the caller or Transformer_base.
    Attributes
    ----------
    status : {'on','off'} | None
        Current commanded status of the boiler. When 'on' the model will
        produce heat according to staged capacity and startup behaviour.
    lag_status : {'on','off'}
        Status during the previous step; used to detect transitions and reset
        startup timers.
    uptime : float
        Time elapsed since the last startup, expressed in minutes.
    time_reset : float
        Timestamp (seconds) when the boiler was last turned on; used to compute uptime.
    Q_demand : float | None
        Current thermal demand assigned to the boiler (W).
    P_th : float
        Thermal power output decided for the current timestep (W). Computed
        from staged capacities and startup regressions before calling
        Transformer_base.step().
    eta : float
        Current thermal efficiency (0..1). During startup this may be computed
        from startup_eta_coeff; otherwise nominal efficiency (nom_eta) is used.
    heat_out_caps : list[float]
        Ordered list of available thermal output stages (W). The model picks the smallest stage >= Q_demand,
        or the largest stage if demand exceeds all stages.
    Method: step(time)
    ------------------
    step(time)
        Advance the boiler model for the simulation time given by `time`.
        - time: simulation timestamp in seconds.
        Algorithm summary:
        1. Select target power stage P_stage by finding the smallest entry in
           heat_out_caps >= Q_demand (or use the largest stage if none match).
        2. Update uptime (minutes): if status is 'on' and a transition from
           'off' was detected, reset time_reset; compute uptime = (time - time_reset)/60.
           If status is 'off' or None, uptime is reset to 0 and P_th set to 0.
        3. If startup_coeff is provided and status == 'on':
           - If uptime < startup_limit, compute instantaneous P_th (kW) via the
             polynomial at uptime (minutes), convert to W (×1000), clamp non-negative.
           - If the configured timestep is long relative to startup (step_size/60 > startup_limit)
             and the unit is at the very start of the step (uptime == 0), compute an
             averaged P_th over the timestep to account for partial-time startup energy.
           - Finally, clamp P_th to be no greater than P_stage.
        4. If no startup_coeff provided, set P_th = P_stage (instant switch to stage).
        5. If startup_eta_coeff is provided, compute eta via its polynomial at uptime
           (minutes). If the timestep spans the startup similarly to above, an averaged
           eta is computed. Eta is clipped to be >= 0.
        6. Call super().step(time) so Transformer_base can use P_th (and eta) to
           compute flows, temperatures, and internal states.
        7. Update lag_status for next-step transition detection.
    Notes and assumptions
    ---------------------
    - Time units: `time` is expected in seconds; uptime and startup_limit are in minutes.
    - Power units: heat_out_caps and P_th are in watts (W). Polynomials in startup_coeff
      are assumed to produce values in kilowatts (kW) and are converted to W inside the model.
    
    Example
    -------
    params = {
        'startup_coeff': [0.0, 0.5],        # P_th(kW) = 0.0 + 0.5 * uptime(min)
        'startup_limit': 5.0,               # minutes
        'startup_eta_coeff': [0.8, 0.02],   # eta = 0.8 + 0.02 * uptime(min)
        'step_size': 60                     # seconds
    }
    boiler = Gboiler(params)
    # set boiler.status, boiler.Q_demand, then call boiler.step(sim_time_seconds)
    """
    def __init__(self, params, *, validate: bool = True):

        super().__init__(params, validate=validate)
        

        self.startup_coeff = params.get('startup_coeff', None) # Future : list of lists, corresponding to each power stage
        self.startup_time = params.get('startup_limit', None)
        self.startup_eta_coeff = params.get('startup_eta_coeff', None)# coefficients to represent lower eta at startup
        self.step_size = None

        #input/outpus
        self.status = None
        self.lag_status = 'off'
        self.uptime = 0
        self.time_reset = 0
        self.Q_demand = None
    def step(self, time):

        P_stage = min((i for i in self.heat_out_caps if i >= self.Q_demand), default=self.heat_out_caps[-1]) #target power stage based on demand
        
        # Counting uptime for startup behaviour
        if self.status == 'off' or self.status is None :
            self.P_th = 0
            self.uptime = 0
            
        else :
          
            if self.status != self.lag_status: #lag_status initialized to off, so when turned on, reset var assigned
                self.time_reset = time
            #to count time passed after each startup. In the previous line, time_reset is assigned the time of initialisation of startup.
            self.uptime = (time - self.time_reset)/60  #the regression model takes time in minutes.
        
        # Determining Pth based on startup behaviour
        if self.startup_coeff and self.status == 'on':            
            if self.uptime < (self.startup_time):
                self.P_th = 0
                for i in range(len(self.startup_coeff)):
                    self.P_th += self.startup_coeff[i] * self.uptime**i #i starts for 0, so will work for intercept as well.
                 
                self.P_th *= 1000 #Regression model was for KW #TODO rectify this!
                if self.P_th < 0:  #for the lack of a better model :)
                    self.P_th = 0
            #When the stepsize is lesser than the start up time of the gen, the energy is scaled accordingly
            if self.step_size/60 > self.startup_time and self.uptime ==0: 
                self.P_th = (0.5 * (self.startup_time/60)*self.heat_out_caps[-1] + ((self.step_size/60-self.startup_time)/60 * self.heat_out_caps[-1]))/(self.step_size/3600)
            
            self.P_th = min(self.P_th, P_stage) #ensuring that the power does not exceed the target power stage, and also allows startup behaviour for part-load       
        
        else: #When startup behaviour not specified
            self.P_th = P_stage
        
        # If regression for efficiency during startup specified   
        if self.startup_eta_coeff:
            self.eta = 0
            for i in range(len(self.startup_eta_coeff)):
                    self.eta += self.startup_eta_coeff[i] * self.uptime**i
            if self.step_size/60 > self.startup_time and self.uptime ==0:
                self.eta = (0.5 * (self.startup_time/60)*self.nom_eta + 
                             ((self.step_size/60-self.startup_time)/60 * self.nom_eta))/(self.step_size/3600)
            self.eta = max(0, self.eta)


        super().step(time) #self.Pth made available now
        # tqdm.write(f'Boiler flow: {self.mdot}')

        self.lag_status = self.status

    def _validate_model_params(self, params, hard_errors):

        name = type(self).__name__
        
        # -------------------- warnings -------------------- 
        if (params.get("startup_coeff", None) is None and params.get("startup_eta_coeff", None) is None) and params.get("startup_limit", None) is not None:
            tqdm.write(
                f"- {name}: 'startup_limit' is defined but no startup coefficients are provided; 'startup_limit' will be ignored."
            )
        # -------------------- constraints (dict rules, per-key) --------------------
        rules = {
            "startup_limit": {
                "required": False,
                "types": (int, float, np.number),
                "pred": lambda v: v > 0,
                "msg": "'startup_limit' must be a number > 0 (minutes) when provided.",
            },
            "startup_coeff": {
                "required": False,
                "types": (list, tuple, np.ndarray),
                "pred": lambda v: (len(v) > 0 and all(isinstance(x, (int, float, np.number)) for x in v)),
                "msg": "'startup_coeff' must be a non-empty list of numbers when provided.",
            },
            "startup_eta_coeff": {
                "required": False,
                "types": (list, tuple, np.ndarray),
                "pred": lambda v: (len(v) > 0 and all(isinstance(x, (int, float, np.number)) for x in v)),
                "msg": "'startup_eta_coeff' must be a non-empty list of numbers when provided.",
            },
        }

        for key, rule in rules.items():
            required = rule.get("required", False)
            types_ = rule.get("types", None)
            pred = rule.get("pred", None)
            msg = rule.get("msg", f"Invalid '{key}'.")
            
            if key not in params or params.get(key, None) is None:
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

        # Cross-field startup requirement
        if params.get("startup_coeff", None) is not None or params.get("startup_eta_coeff", None) is not None:
            sl = params.get("startup_limit", None)
            if not isinstance(sl, (int, float, np.number)) or not (sl > 0):
                hard_errors.append(
                    f"{name}: 'startup_limit' is required and must be > 0 minutes when startup coefficients are provided."
                )
#-------------------------Mosaik Back-end-------------------------------
META = {
    'type': 'time-based',
    'models': {
        'Transformer': {
            'public': True,
            'params': ['params'],
            'attrs': [],
        },
    },
}

class TransformerSimulator(mosaik_api.Simulator):
    def __init__(self):
        
        super().__init__(META)
        self.time_resolution = None
        self.models = dict()  # contains the model instances
        self.sid = None
        self.step_size = None
        self.eid_prefix = "Boiler"
        self.time = 0
        
        
    def init(self, sid, time_resolution, step_size, params, same_time_loop=False):
        self.time_resolution = float(time_resolution)
        if self.time_resolution != 1.0:
            print('WARNING: %s got a time_resolution other than 1.0, which \
                can not be handled by this simulator.', sid)
        self.sid = sid # simulator id
        self.step_size = step_size
        if same_time_loop:
            self.meta['type'] = 'event-based'
        
        self.dummy_object = Gboiler(params, validate=False)
        self.meta['models']['Transformer']['attrs'] = self.dummy_object.get_init_attrs()

        return self.meta
    
    def create(self, num, model, params):
        """Create and register one or more model entities.

        Parameters
        ----------
        num : int
            Number of entities to create.
        model : str
            Model key as exposed in ``META['models']`` (unused but required
            by the Mosaik API).
        params : dict
            Parameters passed to each created model instance.

        Returns
        -------
        list
            A list of entity descriptors as expected by Mosaik.
        """

        entities = []

        next_eid = len(self.models) #if create called a second time, eid will not repeat
        for i in range(next_eid, next_eid + num):
            eid = '%s%d' % (self.eid_prefix, i)
            self.models[eid] = Gboiler(params)
            self.models[eid].step_size = self.step_size #assigning the step size
            entities.append({'eid': eid, 'type': model})
        return entities
            
    def step(self, time, inputs, max_advance):
        """Handle inputs from other simulators and advance all models.

        This method maps incoming attribute values to the corresponding
        model instances, updates the simulator-local step size, calls
        :meth:`Gboiler.step` for each instance, and returns the next
        requested simulation time when running in time-based mode.

        Parameters
        ----------
        time : float
            Current simulation time (seconds).
        inputs : dict
            Mapping of entity ids to input attributes received from other
            simulators.
        max_advance : float
            Maximum time Mosaik allows to advance in this call (unused).

        Returns
        -------
        float or None
            Next requested time (``time + self.step_size``) for time-based
            runs, or ``None`` for event-based runs.
        """

        for eid, attrs in inputs.items():
            if self.meta['type'] == 'event-based':
                if time != self.time:
                    self.time = time
                    setattr(self.models[eid], 'step_executed', False)
            for attr, src_ids in attrs.items():
                if len(src_ids) > 1:
                    raise ValueError('Too many inputs for attribute %s' % attr)
                for val in src_ids.values():
                    setattr(self.models[eid], attr, val)

            self.models[eid].step_size = self.step_size

        for eid, model in self.models.items():
            model.step(time)

        if self.meta['type'] == 'event-based':
            return None
        else:
            return time + self.step_size
    
    def get_data(self, outputs):
        """Return requested output attributes for the given entities.

        Parameters
        ----------
        outputs : dict
            Mapping of entity ids to lists of requested attribute names.

        Returns
        -------
        dict
            Mapping of entity ids to dictionaries of attribute values. The
            returned mapping includes a ``time`` key holding the simulator's
            current time.
        """

        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr not in self.meta['models']['Transformer'][
                        'attrs']:
                    raise ValueError('Unknown output attribute: %s' % attr)
                data['time'] = self.time
                data[eid][attr] = getattr(self.models[eid], attr)
                    
        return data

def main():
    return mosaik_api.start_simulation(TransformerSimulator())

if __name__ == '__main__':
    main()