import mosaik_api
from src.models.EnTransformer import IncompleteConfigError, OverdefinedConfig, Transformer_base
from src.models.boiler_model_v2 import Gboiler
import warnings

class CHP(Gboiler):

    def __init__(self, params):
        super().__init__(params)
        
        self.nom_P_el = params.get('P_el', None) # TODO: warning (or error) if this is None
        self.elec_share = params.get('elec_share', None) # TH to EL ratio, P_el / P_th
        self.startup_coeff = params.get('startup_coeff') # Future : list of lists, corresponding to each power stage
        self.startup_time = params.get('startup_limit')
        self.step_size = None

        if self.nom_P_el:
            self.elec_share = self.nom_P_el/self.nom_P_th #More intuitive to have the nominal power defined by the user.
        self.P_el = None

    

    def step(self, time):

        super().step(time)

        if self.elec_share:
            self.P_el = self.P_th * self.elec_share 

    def _validate_model_params(self, params, hard_errors):
            # Keep boiler validation structure/behavior 
            super()._validate_model_params(params, hard_errors)
            
            if params.get("P_el", None) is None and params.get("elec_share", None) is None:
                warnings.warn(
                    "CHP: neither 'P_el' nor 'elec_share' provided, CHP will default to 0 electrical power output.", 
                    UserWarning
                )

            # over-definition warnings
            if params.get("P_el", None) is not None and params.get("elec_share", None) is not None:
                warnings.warn(
                    "CHP: both 'P_el' and 'elec_share' provided, 'P_el' will be used to compute 'elec_share'.",
                    OverdefinedConfig,
                )

            # constraints loop (collect all issues, raise once)
            checks = []

            if params.get("P_el", None) is not None:
                checks.append((
                    isinstance(params.get("P_el"), (int, float)) and params.get("P_el") > 0,
                    "'P_el' must be a number > 0 (W) when provided.",
                ))

            
            if params.get("elec_share", None) is not None:
                checks.append((
                    isinstance(params.get("elec_share", None), (int, float)) and 0 < params.get("elec_share", None) <= 1,
                    "'elec_share' must be a number > 0 and <= 1 when provided (P_el / P_th).",
                ))

            for ok, msg in checks:
                if not ok:
                    hard_errors.append(msg)

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
        self.eid_prefix = None
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

        self.eid_prefix = params.get('eid_prefix')
        
        self.dummy_object = CHP(params)
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