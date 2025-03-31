import pytest
import sys
import os

current_dir = os.path.dirname(os.path.abspath("__file__"))  # Jupyter fallback
main_dir = os.path.abspath(os.path.join(current_dir, '..'))


# Add 'src' to Python path
sys.path.insert(0, main_dir)

from models.controller import Controller

    

@pytest.fixture(autouse=True)
def init_params():
    # In a more general feature/ integration test; these params could be imported from main.
    # Here this allows us to modify params, as params['..'] = ...
    params_hwt = {
        'height': 2500,
        'volume': 5000,
        'T_env': 20.0,
        'htc_walls': 0.28,
        'htc_layers': 0.897,
        'n_layers': 3,
        'n_sensors': 3,
        'connections': {
            'heat_in': {'pos': 150},
            'heat_out': {'pos': 2350},
            'chp_in': {'pos': 2300},
            'chp_out': {'pos': 50},
            'hp_in': {'pos': 2200},
            'hp_out': {'pos': 100},
            'boiler_in' : {'pos' : 2400},
            'boiler_out' : {'pos' : 120},
            'heat_out2' : {'pos' : 2400},
            'heat_in2' : {'pos' : 200}
        },
        'heating_rods': {
            'hr_1' : {
                'mode' : 'on',
                'pos' : 2200,
                'P_th_stages' : [0, 500, 1000, 2000, 10000],
                'T_max' : 65, # could assign setpoint attr directly here!,
                'eta' : 1 }}
    }
    
    params = {
    'T_hp_sp_h': 35,
    'T_chp_h' : 75,
    'T_hp_sp_l': 35,
    'T_hr_sp': 65,
    'heat_rT' : 35,
    'operation_mode': 'heating',
    'control_strategy': '5',
    'hr_mode' : 'off',
    'supply_config' : '3-runner',
    'sh_out' : '1',         #0 for first tank, 1 for 2nd tank...
    'dhw_out' : '2',
    'boiler_mode': 'on',
    'step_size' : 15*60,
    'params_hwt': params_hwt
}

@pytest.fixture
def set_inputs():
    ctrls_inputs = {
    'T_amb': None,
    'heat_demand': None,
    'dhw_demand': None,
    'sh_demand': None,
    'tes0_heat_out_F': None,
    'tes0_heat_in_F': None,
    'tes0_hp_out_F': None,
    'hp_in_F': None,
    'tes1_hp_out_F': None,
    'tes1_heat_out_F': None,
    'tes1_heat_out_T': None,
    'tes1_hp_out_T': None,
    'tes1_heat_out2_F': None,
    'tes0_heat_out_T': None,
    'hp_out_T': None,
    'bottom_layer_Tank0': None,
    'tes0_heat_out2_T': None,
    'tes0_heat_out2_F': None,
    'hp_out_T': None,
    'tes1_hp_out_F': None,
    'tes1_heat_out_F': None,
    'tes2_hp_out_F': None,
    'tes2_heat_out_F': None,
    'T_amb': None,
    'T_mean_hwt': None,
    'hwt_mass': None,
    'top_layer_Tank1': None,
    'hp_out_T': None,
    'tes2_heat_out2_F': None,
    'tes2_hp_out_T': None,
    'tes2_hp_out_F': None,
    'T_env': None,
    'hr_1.P_th_set': None,
    'hr_1.P_th_set': None,
    'hr_1.P_th_set': None,
    'boiler_supply': None,
    'boiler_uptime': None,
    'boiler_mdot': None,
    'boiler_demand': None,
    'boiler_status': None,
    'chp_supply': None,
    'chp_uptime': None,
    'chp_mdot': None,
    'chp_demand': None,
    'chp_status': None,
    'hp_supply': None,
    'hp_on_fraction': None,
    'hp_cond_m': None
}
    for i in ctrls_inputs.keys():
        setattr(controller_obj)

def test_calc_heat_supply():
    params['sh_out'] = 1
    controller_obj = Controller(params)

    with pytest.raises(TypeError):
        controller_obj.calc_heat_supply(controller_obj.config)