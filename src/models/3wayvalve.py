import mosaik_api
from src.utils import helpers

class ThreeWayValve():
    '''
    A class representing a three-way valve.
    It takes an input flow and splits it into two output flows based on a defined share.
    The temperature is assumed to be the same for all flows.
    Attributes:
    - flows: A dictionary containing the input and output flows.
    - out1_share: The fraction of the input flow that goes to output 1. Could be preset in the params, or also dynamically assigned by another entity.
    - out2_share(optional) : The fraction of the input flow that goes to output 2. If provided, out1_share is adjusted accordingly.
    
    '''
    def __init__(self, params={}):
    
        self.flows = {
            'in' : 0,
            'out_1' : 0,
            'out_2' : 0,
            'temp' : 0
        } 
        self.out1_share = params.get('out1_share', 0.5) # how much of the input flow goes to out_1
        if 'out2_share' in params.keys():
            self.out1_share = 1 - params.get('out2_share')

    
    def step(self, time):

        self.flows['out_1'] = self.flows['in'] * self.out1_share
        self.flows['out_2'] = self.flows['in'] * (1 - self.out1_share)

    def get_init_attrs(self):
        '''
        Simply returns a list of all user defined attributes in this class. 
        Useful to add to the attrs list in META.
        '''
        attr_list = helpers.flatten_attrs(self, list(vars(self).keys()))
        return attr_list

#-------------------------Mosaik Back-end-------------------------------
META = {
    'type': 'time-based',
    'models': {
        'Valve': {
            'public': True,
            'params': ['params'],
            'attrs': ['status'],
        },
    },
}

class SimInterface(mosaik_api.Simulator):
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
        
        self.dummy_object = ThreeWayValve(params)
        self.meta['models']['Valve']['attrs'] = self.dummy_object.get_init_attrs()
        # self.meta['models']['Transformer']['trigger'] = self.dummy_object.get_init_attrs()

        return self.meta
    
    def create(self, num, model, params):
        entities = []

        next_eid = len(self.models) #if create called a second time, eid will not repeat
        for i in range(next_eid, next_eid + num):
            eid = '%s%d' % (self.eid_prefix, i)
            self.models[eid] = ThreeWayValve(params)
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
                    helpers.set_nested_attr(self.models[eid], attr, val)

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
                if attr not in self.meta['models']['Valve'][
                        'attrs']:
                    raise ValueError('Unknown output attribute: %s' % attr)
                data['time'] = self.time
                data[eid][attr] = helpers.get_nested_attr(self.models[eid], attr)
                    
        return data

def main():
    return mosaik_api.start_simulation(SimInterface())

if __name__ == '__main__':
    main()