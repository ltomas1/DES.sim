"""
Mosaik interface for controller model

"""
import mosaik_api
from models.controller import Controller

META = {
    'type': 'time-based',
    'models': {
        'Controller': {
            'public': True,
            'params': ['params'],
            'attrs': ['_'],
        },
    },
}

#The following attrs appended to the attrs entry in META dict.
hp_attrs = ['hp_demand', 'hp_out_T', 'T_amb', 'heat_source_T']
chp_attrs = ['chp_demand', 'chp_out_T', 'chp_status', 'chp_uptime']
hwt_attrs = ['heat_in_F', 'heat_in_T', 'heat_out_F', 'T_amb_hwt', 'hp_in_T',
             'hp_out_F', 'hp_in_F', 'chp_in_T', 'chp_in_F', 'chp_out_F',
             'tes0_heat_out_T', 'tes0_heat_out_F', 'tes0_heat_in_F', 'tes0_hp_out_F',
             'tes1_heat_out_T', 'tes1_heat_out_F', 'tes1_hp_in_F', 'tes1_hp_out_T', 'tes1_hp_out_F',
             'tes2_heat_out_F',  'tes2_hp_out_T', 'tes2_hp_out_F']
db_attrs = ['heat_supply', 'heat_demand', 'hp_supply', 'chp_supply',
            'T_mean_hwt', 'hwt_mass', 'hwt_hr_P_th_set', 'hp_on_fraction', 'hp_cond_m', 'heat_out_T', 'chp_mdot',
            'P_hr', 'T_room', 'bottom_layer_T','bottom_layer_T_chp', 'top_layer_T']
boiler_attrs = ['boiler_demand', 'boiler_mdot', 'boiler_supply', 'boiler_status']


class ControllerSimulator(mosaik_api.Simulator):
    def __init__(self):
        super().__init__(META)

        self.models = dict()  # contains the model instances
        self.sid = None
        self.eid_prefix = 'Controller_'
        self.step_size = None
        self.async_requests = dict()
        self.time = None
        self.step_executed = False
        self.first_iteration = None
        self.final_iteration = False

    def init(self, sid, time_resolution, step_size, same_time_loop=False):
        self.time_resolution = float(time_resolution)
        if self.time_resolution != 1.0:
            print('WARNING: %s got a time_resolution other than 1.0, which \
                can not be handled by this simulator.', sid)
        self.sid = sid # simulator id
        self.step_size = step_size
        if same_time_loop:
            self.meta['type'] = 'event-based'
        self.meta['models']['Controller']['attrs'] += hp_attrs + chp_attrs + hwt_attrs + db_attrs + boiler_attrs
        return self.meta

    def create(self, num, model, params=None):
        entities = []

        next_eid = len(self.models)
        for i in range(next_eid, next_eid + num):
            eid = '%s%d' % (self.eid_prefix, i)
            if params is not None:
                self.models[eid] = Controller(params)
            else:
                self.models[eid] = Controller()
            entities.append({'eid': eid, 'type': model})
        return entities

    def step(self, time, inputs, max_advance):
        if self.meta['type'] == 'event-based':
            if self.time != time:
                self.first_iteration = True
                self.final_iteration = False
                self.step_executed = False
                self.time = time
            elif self.step_executed:
                if not self.final_iteration:
                    self.first_iteration = False
                    self.final_iteration = True
                else:
                    self.final_iteration = False
        for eid, attrs in inputs.items():
            for attr, src_ids in attrs.items():
                if len(src_ids) > 1:
                    raise ValueError('Two many inputs for attribute %s' % attr)
                for val in src_ids.values():
                    setattr(self.models[eid], attr, val)
            if self.meta['type'] == 'event-based':
                if not self.step_executed:
                    self.models[eid].step_size = self.step_size
                    self.models[eid].step(time)
                    self.step_executed = True
            else:
                self.models[eid].step_size = self.step_size
                self.models[eid].step(time)

        if self.meta['type'] == 'event-based':
            return None
        else:
            return time + self.step_size

    def get_data(self, outputs):
        data = {}
        data['time'] = self.time
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr not in self.meta['models']['Controller'][
                        'attrs']:
                    raise ValueError('Unknown output attribute: %s' % attr)
                if self.meta['type'] == 'event-based':
                    if self.first_iteration and (attr in hp_attrs or attr in db_attrs or attr in chp_attrs):
                        data[eid][attr] = getattr(self.models[eid], attr)
                    elif self.final_iteration and attr in hwt_attrs:
                        if attr == 'T_amb_hwt':
                            data[eid][attr] = getattr(self.models[eid], 'T_amb')
                        else:
                            data[eid][attr] = getattr(self.models[eid], attr)
                else:
                    data[eid][attr] = getattr(self.models[eid], attr)
        return data

def main():
    return mosaik_api.start_simulation(ControllerSimulator())


if __name__ == '__main__':
    main()
