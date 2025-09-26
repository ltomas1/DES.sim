# -*- coding: utf-8 -*-
"""
A simple data collector that prints all data when the simulation finishes.

"""
import collections
import mosaik_api_v3 as api

META = {
    "type": "event-based",
    "models": 
        {"Collector": 
            {"public": True, 
             "any_inputs": True, 
             "params": [], 
             "attrs": ['buffer']}},
    "extra_methods": ["dump"],  # expose a method callable from the scenario
}

class Collector(api.Simulator):
    def __init__(self):
        super().__init__(META)
        self.eid = None
        self.data = collections.defaultdict(lambda: collections.defaultdict(dict))

    def init(self, sid, time_resolution):
        return self.meta

    def create(self, num, model):
        self.eid = "Monitor"
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        for attr, by_src in inputs.get("Monitor", {}).items():
            for src, value in by_src.items():
                self.data[src][attr][time] = value

    # extra method to pull everything after the run
    def dump(self):
        return self.data
