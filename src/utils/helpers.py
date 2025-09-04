'''
This file will have a few helper functions, used accros this repo.
'''
import csv
import os


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

debug_log= {}

def debug_trace(time, attrs, entity, filename = 'debug_Log.csv'):
    global debug_log
    if not debug_log:
        debug_log = {}
        debug_log['time'] = []
    for attr in attrs:
        if attr not in debug_log.keys():
            debug_log[attr] = []

        debug_log['time'].append(time)
        debug_log[attr].append(get_nested_attr(entity, attr))

    path = os.getcwd()     
    filepath = os.path.join(os.getcwd(), filename)
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=debug_log.keys())
        writer.writeheader()
        for row in zip(*debug_log.values()):
            writer.writerow(dict(zip(debug_log.keys(), row)))
