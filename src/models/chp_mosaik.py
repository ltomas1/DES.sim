# -*- coding: utf-8 -*-
"""
Mosaik interface for Leroy's CHP model

"""

import mosaik_api
from models.chp_model import CHP

META = {
    'type': 'time-based',
    'models': {
        'CHP': {
            'public': True,
            'params': ['params'],
            'attrs': ['eff_el', 'nom_P_th', 'mdot', 'mdot_neg', 'temp_in', 'Q_Demand', 'cp', 'temp_out', 'P_th', 'P_el'],
        },
    },
}


class CHPSimulator(mosaik_api.Simulator):
    def __init__(self):
        super().__init__(META)
        self.time_resolution = None
        self.models = dict()  # contains the model instances
        self.sid = None
        self.eid_prefix = 'CHP_'
        self.step_size = None
        self.time = 0
        
        
    def init(self, sid, time_resolution, step_size, same_time_loop=False):
        self.time_resolution = float(time_resolution)
        if self.time_resolution != 1.0:
            print('WARNING: %s got a time_resolution other than 1.0, which \
                can not be handled by this simulator.', sid)
        self.sid = sid # simulator id
        self.step_size = step_size
        if same_time_loop:
            self.meta['type'] = 'event-based'

        return self.meta
    
    def create(self, num, model, params):
        entities = []

        next_eid = len(self.models)
        for i in range(next_eid, next_eid + num):
            eid = '%s%d' % (self.eid_prefix, i)
            self.models[eid] = CHP(params)
            entities.append({'eid': eid, 'type': model})
        return entities
            
    def step(self, time, inputs, max_advance):
        for eid, attrs in inputs.items():
            if self.meta['type'] == 'event-based':
                if time != self.time:
                    self.time = time
                    setattr(self.models[eid].state, 'step_executed', False)
            for attr, src_ids in attrs.items():
                if len(src_ids) > 1:
                    raise ValueError('Too many inputs for attribute %s' % attr)
                for val in src_ids.values():
                    setattr(self.models[eid].inputs, attr, val)

            self.models[eid].inputs.step_size = self.step_size

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
                if attr not in self.meta['models']['CHP'][
                        'attrs']:
                    raise ValueError('Unknown output attribute: %s' % attr)
                data['time'] = self.time
                data[eid][attr] = float(getattr(self.models[eid].state, attr))
                    
        return data

def main():
    return mosaik_api.start_simulation(CHPSimulator())

if __name__ == '__main__':
    main()

