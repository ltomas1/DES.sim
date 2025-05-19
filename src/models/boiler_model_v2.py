import mosaik_api
from src.models.EnTransformer import Transformer_base

class Gboiler(Transformer_base):

    def __init__(self, params):
        
        super().__init__(params)
        
        # self.elec_out_cap = params.get('elec_out', None)
        # self.elec_share = params.get('elec_share', None) 
        # self.startup_coeff = params.get('startup_coeff') # Future : list of lists, corresponding to each power stage
        # self.startup_time = params.get('startup_limit')
    def step(self, time):

        super().step(time)

#-------------------------(Not implemented here) Mosaik Back-end-------------------------------
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
        
        self.dummy_object = Gboiler(params)
        self.meta['models']['Transformer']['attrs'] = self.dummy_object.get_init_attrs()

        return self.meta
    
    def create(self, num, model, params):
        entities = []

        next_eid = len(self.models) #if create called a second time, eid will not repeat
        for i in range(next_eid, next_eid + num):
            eid = '%s%d' % (self.eid_prefix, i)
            self.models[eid] = Gboiler(params)
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
                data[eid][attr] = float(getattr(self.models[eid], attr))
                    
        return data

def main():
    return mosaik_api.start_simulation(TransformerSimulator())

if __name__ == '__main__':
    main()