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

class IncompleteConfigError(Exception) : pass

class Transformer():
    def __init__(self, params):

        self.eid_prefix = params.get('eid_prefix')
        self.heat_out_caps = params.get('heat_out')# list
        self.elec_out_cap = params.get('elec_out', None)
        self.elec_share = params.get('elec_share', None) 
        self.startup_coeff = params.get('startup_coeff') # Future : list of lists, corresponding to each power stage
        self.startup_time = params.get('startup_limit')
        self.cp = params.get('cp', 4187)
        self.set_temp = params.get('set_temp', None)
        self.set_flow = params.get('set_flow', None)
        self.step_size = None

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
            
            
            
            
            if len(self.heat_out_caps) <=2 and self.uptime < (self.startup_time):
                self.P_th = 0
                for i in range(len(self.startup_coeff)):
                    self.P_th += self.startup_coeff[i] * self.uptime**i #i starts for 0, so will work for intercept as well.
                
                self.P_th *= 1000 #Regression model was for KW #TODO rectify this!
                if self.P_th < 0:  #for the lack of a better model :)
                    self.P_th = 0
            if self.step_size/60 > self.startup_time and self.uptime ==0:
                self.P_th = (0.5 * (self.startup_time/60)*self.heat_out_caps[-1] + ((self.step_size/60-self.startup_time)/60 * self.heat_out_caps[-1]))/(self.step_size/3600)

        self.P_el = self.P_th/self.elec_share        
        
        
        if self.set_temp:
            self.temp_out = self.set_temp
            self.mdot = self.P_th/(self.cp * (self.temp_out - self.temp_in))
            self.mdot = max(0, self.mdot) #To prevent reverse flow!
            
        elif self.set_flow:
            self.mdot = self.set_flow
            
            self.temp_out = ( self.P_th / (self.mdot * self.cp))  + self.temp_in

        else :
            raise IncompleteConfigError("Atleast one 'set_flow' or 'set_temp' needs to be defined!")

        self.mdot_neg = -1 * self.mdot

        self.lag_status = self.status

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
        
        self.dummy_object = Transformer(params)
        self.meta['models']['Transformer']['attrs'] = self.dummy_object.get_init_attrs()

        return self.meta
    
    def create(self, num, model, params):
        entities = []

        next_eid = len(self.models) #if create called a second time, eid will not repeat
        for i in range(next_eid, next_eid + num):
            eid = '%s%d' % (self.eid_prefix, i)
            self.models[eid] = Transformer(params)
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