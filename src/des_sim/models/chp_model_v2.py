import mosaik_api
import numpy as np
from tqdm import tqdm
from des_sim.models.EnTransformer import Transformer_base
from des_sim.models.boiler_model_v2 import Gboiler

class CHP(Gboiler):

    def __init__(self, params, *, warn: bool = True):
        super().__init__(params, warn=warn)

        self.nom_P_el = params.get('P_el', None)
        self.elec_share = params.get('elec_share', None) # TH to EL ratio, P_el / P_th

        if self.nom_P_el and self.nom_P_th > 0:
            self.elec_share = self.nom_P_el/self.nom_P_th #More intuitive to have the nominal power defined by the user.
        self.P_el = None

    

    def step(self, time):

        super().step(time)

        if self.elec_share:
            self.P_el = self.P_th * self.elec_share 

    def _validate_model_params(self, params, hard_errors, *, warn: bool = True):
        # Keep boiler validation structure/behavior 
        super()._validate_model_params(params, hard_errors, warn=warn)
        name = type(self).__name__

        #-------------------- warnings -------------------- 
        if warn:
            if params.get("P_el", None) is not None and (params.get("elec_share", None) is not None and params.get("nom_P_th", None) is not None):
                tqdm.write(
                    f"- {name}: both 'P_el' and 'elec_share and 'nom_P_th' provided, 'P_el' will be used to compute 'elec_share'."
                )
        # -------------------- constraints (dict rules, per-key) --------------------
        rules = {
            "P_el": {
                "required": False,
                "types": (int, float, np.number),
                "pred": lambda v: v > 0,
                "msg": "'P_el' must be a number > 0 (W) when provided.",
            },
            "elec_share": {
                "required": False,
                "types": (int, float, np.number),
                "pred": lambda v: 0 < v <= 1,
                "msg": "'elec_share' must be a number in (0, 1] when provided (P_el / P_th).",
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
        # -------------------- cross-field required logic --------------------
        if params.get("P_el", None) is None and params.get("elec_share", None) is None:
            hard_errors.append(
                f"{name}: At least one of 'P_el' or 'elec_share' must be provided to define electrical output."
            )

    def get_init_attrs(self):
        '''
        Simply returns a list of all user defined attributes in this class. 
        Useful to add to the attrs list in META.
        '''
        return list(vars(self).keys())

#-------------------------Mosaik Back-end-------------------------------
META = {
    'type': 'time-based',
    'models': {
        'Transformer': {
            'public': True,
            'params': ['params'],
            'attrs': ['status'],
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
        self.eid_prefix = "CHP"
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
        
        self.dummy_object = CHP(params, warn=False)
        self.meta['models']['Transformer']['attrs'] = self.dummy_object.get_init_attrs()

        return self.meta
    
    def create(self, num, model, params):
        entities = []

        next_eid = len(self.models) #if create called a second time, eid will not repeat
        for i in range(next_eid, next_eid + num):
            eid = '%s%d' % (self.eid_prefix, i)
            self.models[eid] = CHP(params)
            self.models[eid].step_size = self.step_size
            entities.append({'eid': eid, 'type': model})
        return entities
            
    def step(self, time, inputs, max_advance):
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