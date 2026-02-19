import mosaik_api

class Battery():
    """Generic simplified battery storage model.

    The class accepts a dictionary of `params` describing the battery
    capabilities such as nominal capacity, charge and discharge efficiencies.

    Parameters:
    - params (dict): configuration keys used by the transformer. Common keys:
        - 'nom_capacity' (float or int): nominal capacity of the battery storage (Wh)
        - 'charge_eff' (float): efficiency for charging the battery (0-1)
        - 'max_charge_power' (float): maximum power for charging the battery (W)
    """
    def __init__(self, params):
        
        self.nom_capacity = params.get('nom_capacity', None) 
        self.charge_eff = params.get('charge_eff', None) 
        self.discharge_eff = params.get('discharge_eff', self.charge_eff)
        self.max_charge_power = params.get('max_charge_power', None) 
        self.max_discharge_power = params.get('max_discharge_power', self.max_charge_power)

        self.soc = 0                # % of nominal capacity      
        self.P_el_in = None         # W
        self.P_el_out = None        # W
        self.step_size = None

    def step(self, time):
        # limit P_el_in to max_charge_power
        if self.max_charge_power is not None and self.P_el_in is not None:
            self.P_el_in = min(self.P_el_in, self.max_charge_power)
        
        # limit P_el_out to max_discharge_power
        if self.max_discharge_power is not None and self.P_el_out is not None:
            self.P_el_out = min(self.P_el_out, self.max_discharge_power)

        # calculate new state of charge
        if self.P_el_in is not None:
            self.soc += ((self.P_el_in * self.charge_eff) * (self.step_size / 3600)) / self.nom_capacity * 100
        if self.P_el_out is not None:
            self.soc -= ((self.P_el_out / self.discharge_eff) * (self.step_size / 3600)) / self.nom_capacity * 100
       
        # ensure soc is within 0-100%
        if self.soc > 100:
            self.P_el_in = self.P_el_in - (((self.soc - 100) / 100) * self.nom_capacity) / (self.charge_eff * (self.step_size / 3600))
        
        if self.soc < 0:
            self.P_el_out = self.P_el_out - ((-self.soc / 100) * self.nom_capacity) * self.discharge_eff / (self.step_size / 3600)

        self.soc = max(0, min(100, self.soc))

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
        'Battery': {
            'public': True,
            'params': ['params'],
            'attrs': ['status'],
        },
    },
}

class BatterySimulator(mosaik_api.Simulator):
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
        
        self.dummy_object = Battery(params)
        self.meta['models']['Battery']['attrs'] = self.dummy_object.get_init_attrs()

        return self.meta
    
    def create(self, num, model, params):
        entities = []

        next_eid = len(self.models) #if create called a second time, eid will not repeat
        for i in range(next_eid, next_eid + num):
            eid = '%s%d' % (self.eid_prefix, i)
            self.models[eid] = Battery(params)
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
                if attr not in self.meta['models']['Battery'][
                        'attrs']:
                    raise ValueError('Unknown output attribute: %s' % attr)
                data['time'] = self.time
                data[eid][attr] = getattr(self.models[eid], attr)
                    
        return data

def main():
    return mosaik_api.start_simulation(BatterySimulator())

if __name__ == '__main__':
    # minimal example to test the Battery model
    print("Testing Battery Model")
    print("-" * 50)
    
    # Create a battery with 10 kWh capacity
    params = {
        'nom_capacity': 10000,  # 10 kWh in Wh
        'charge_eff': 0.95,     # 95% charging efficiency
        'max_charge_power': 5000,  # 5 kW max charge power
    }
    
    battery = Battery(params)
    battery.step_size = 3600  # 1 hour in seconds
    
    print(f"Battery capacity: {battery.nom_capacity} Wh")
    print(f"Initial SOC: {battery.soc:.2f}%\n")
    
    # Simulate charging at 2 kW for 3 hours
    print("Charging at 1000W for 3 hours:")
    battery.P_el_in = 2000  # 2 kW
    for hour in range(1, 10):
        battery.step(hour * 3600)
        print(f"    P_el_in: {battery.P_el_in} W, P_el_out: {battery.P_el_out} W")
        print(f"  Hour {hour}: SOC = {battery.soc:.2f}%")
    
    battery.P_el_in = None
    print()
    
    # Simulate discharging at 1.5 kW for 2 hours
    print("Discharging at 1000W for 2 hours:")
    battery.P_el_out = 1000  # 1.5 kW
    for hour in range(4, 6):
        battery.step(hour * 3600)
        print(f"  Hour {hour}: SOC = {battery.soc:.2f}%")
        print(f"    P_el_in: {battery.P_el_in} W, P_el_out: {battery.P_el_out} W")
    
    print(f"\nFinal SOC: {battery.soc:.2f}%")
