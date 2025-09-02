'''
This file will have a few helper functions, used accros this repo.
'''

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