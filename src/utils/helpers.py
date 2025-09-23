'''
This file will have a few helper functions, used accros this repo.
'''
import csv
import os
import numpy as np
import pandas as pd


def safe_get(lst, index, default=None):
        """Return lst[index] if it exists, else return default."""
        try:
            return lst[index]
        except IndexError:
            return default
        
def get_nested_attr(entity, attr): #Inspired from mosaik HWT model
    """
    Recursively access a nested attribute or dictionary key.

    Args:
        entity (object | dict): The root object or dictionary to access.
        attr (str): A dot-separated string representing the path 
                    (e.g. "tank_connections.tank1.heat_out2_F").

    Returns:
        Any: The value of the nested attribute or key.

    Raises:
        RuntimeError: If any part of the path is missing in the object/dict.
    """
    attr_parts = attr.split('.')
    val = entity
    
    #The following have been added only to allow for the debug ethod in hotwater tank:(
    if hasattr(entity, 'sensors'): #checking if it's a tank
        if attr_parts[0] in entity.sensors:
            return getattr(entity.sensors[attr_parts[0]],
                    attr_parts[1])
        elif attr_parts[0] in entity.connections:
            return float(getattr(entity.connections[attr_parts[0]],
                    attr_parts[1]))
        elif attr_parts[0] in entity.heating_rods:
            return getattr(entity.heating_rods[attr_parts[0]],
                    attr_parts[1])
    #-------------------------------------------------
    #The actual stuff:
    for level in attr_parts:
        try:
            val = val[level] if isinstance(val, dict) else getattr(val, level)
        except (KeyError, AttributeError) as e:
            raise RuntimeError(f'Missing {level} in {val}') from e
    
    
    return val

def set_nested_attr(entity, attr, val): 
    """
    Recursively set a nested attribute or dictionary key.

    Args:
        entity (object | dict): The root object or dictionary to modify.
        attr (str): A dot-separated string representing the path 
                    (e.g. "tank_connections.tank1.heat_out2_F").
        val (Any): The value to set.

    Raises:
        RuntimeError: If any part of the path (except the last) 
                    is missing in the object/dict.
    """
    
    attr_parts = attr.split('.')
    for level in attr_parts[:-1]:
        try:
            entity = entity[level] if isinstance(entity, dict) else getattr(entity, level)
        except (KeyError, AttributeError) as e:
            raise RuntimeError(f'Missing {level} in {entity}') from e
    if isinstance(entity, dict):
        entity[attr_parts[-1]] = val
    else:
        setattr(entity, attr_parts[-1], val)

def flatten_attrs(entity, attrs):
    flat_keys = []
    for attr in attrs:
            value = getattr(entity, attr)   # get the actual object
            if isinstance(value, dict):
                for key, val in value.items():
                    if isinstance(val, dict):  # nested dict case
                        for subkey in val.keys():
                            flat_keys.append(f"{attr}.{key}.{subkey}")
                    else:
                        flat_keys.append(f"{attr}.{key}")

    return flat_keys


def debug_trace(time, attrs, entity, filename = 'debug_Log.csv', debug_log = {}, print_csv  = True, keyword = '', cycle = 0):
    model = filename.strip('_trace.csv')
    if not debug_log:
        debug_log = {}
        debug_log[model+'time'] = []
        debug_log[model+'cycle'] = [] # to keep track of subcycles in event-based sim
    # inputs received in form of a dict, with attr name and val
    if isinstance(attrs, dict):
        for attr, v in attrs.items():
            for _, val in v.items():
                if attr+keyword not in debug_log.keys():
                    debug_log[attr+keyword] = []
                debug_log[model+'time'].append(time)
                debug_log[model+'cycle'].append(cycle)
                debug_log[attr+keyword].append(val)
    
    elif isinstance(attrs, list):
        for attr in attrs:
            # attr = attr+keyword #to distinguish input and output
            if attr+keyword not in debug_log.keys():
                debug_log[attr+keyword] = []

            debug_log[model+'time'].append(time)
            debug_log[model+'cycle'].append(cycle)
            debug_log[attr+keyword].append(get_nested_attr(entity, attr))
            if not print_csv:
                print(f'attr: {attr}, val : {get_nested_attr(entity, attr)}')
    # print(debug_log)

    path = os.getcwd()     
    filepath = os.path.join(os.getcwd(), filename)
    if print_csv:
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=debug_log.keys())
            writer.writeheader()
            for row in zip(*debug_log.values()):
                writer.writerow(dict(zip(debug_log.keys(), row)))


    return debug_log

def calc_energy(vars, step_size): 

    '''
    
    Calculate energy in Wh from power in W and time step in seconds.
    vars: nested List, pandas series or dataframe only!!!
    step_size: in seconds
    returns absolute value of energy in Wh
    '''
   
    for i in range(len(vars)):
        if isinstance(vars[i], (int, float)):
            vars[i] = 0
        elif isinstance(vars[i], list):
            vars[i] = sum(vars[i]) * step_size/3600
        else :
            # so, pandas series, or dataframes!!
            vars[i] = vars[i].sum() * step_size/3600 
    

    
    
    return np.abs(vars)