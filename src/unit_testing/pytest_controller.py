import pytest
import sys
import os

import pandas as pd

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
    'control_strategy': '1',
    'hr_mode' : 'off',
    'supply_config' : '3-runner',
    'sh_out' : '1',         #0 for first tank, 1 for 2nd tank...
    'dhw_out' : '2',
    'boiler_mode': 'on',
    'step_size' : 15*60,
    'params_hwt': params_hwt
}

    return params

@pytest.fixture(autouse=True)
def set_inputs():

    

    ctrls_inputs = {
    'T_amb': 5,
    'heat_demand': 50,
    'dhw_demand': 20,
    'sh_demand': 30,
    'tes0_heat_out_F': None,
    'tes0_heat_in_F': None,
    'tes0_hp_out_F': None,
    'hp_in_F': None,
    'tes1_hp_out_F': None,
    'tes1_heat_out_T': None,
    'tes1_hp_out_T': None,
    'tes1_heat_out2_F': None,
    'tes0_heat_out_T': None,
    'bottom_layer_Tank0': None,
    'tes0_heat_out2_T': 0,
    'tes0_heat_out2_F': 0,
    'tes1_heat_out_F': None,
    'tes2_hp_out_F': None,
    'tes2_heat_out_F': None,
    'T_mean_hwt': None,
    'hwt_mass': 5000,
    'top_layer_Tank1': None,
    'hp_out_T': None, #hwt0_hpout
    'tes2_heat_out2_F': None,
    'tes2_hp_out_T': None,
    'T_env': None,
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
    'hp_cond_m': None,
    'tes1_heat_out2_T' : None,
    'tes2_heat_out2_T' : None,
    'hr_1.P_th_set' : None,
    'tes2_heat_out_T' : None

}
    # Using values from a previous run as input, can be modified individually aswell.
    df = pd.read_csv(os.path.join(main_dir, 'utils/results.csv'), index_col=0)
    column_match = {
        'T_amb': 'T_amb',
        # 'heat_demand': 'Heat Demand [KW]',
        'heat_demand': None,
        'dhw_demand': None, #manual
        'sh_demand': None,  #manual
        'tes0_heat_out_F': 'HWTSim0_heatout_F',
        'tes0_heat_in_F': 'HWTSim0_heatin_F',
        'tes0_hp_out_F': 'HWTSim0_hp_out_F',
        'hp_in_F': 'HWTSim0_hp_in_F',
        'tes1_hp_out_F': 'HWTSim1_hp_out_F',
        'tes1_heat_out_T': 'HWTSim1_heatout_T',
        'tes1_hp_out_T': 'HWTSim1_hp_out_T',
        'tes1_heat_out2_F': 'HotWaterTankSim-1.HotWaterTank_0-heat_out2.F',
        'tes1_heat_out2_T' : 'HotWaterTankSim-1.HotWaterTank_0-heat_out2.T',
        'tes0_heat_out_T': 'HWTSim0_heatout_T',  
        'bottom_layer_Tank0': 'HWTSim0_sensor0_T',  
        'tes0_heat_out2_T': 'HotWaterTankSim-0.HotWaterTank_0-heat_out2.T',   # manual
        'tes0_heat_out2_F': 'HotWaterTankSim-0.HotWaterTank_0-heat_out2.F',   # Closest match (as no direct match found)
        'tes1_heat_out_F': 'HWTSim1_heatout_F',
        'tes2_hp_out_F': 'HWTSim2_hp_out_F',
        'tes2_heat_out_F': 'HWTSim2_heatout_F',
        'tes2_heat_out_T' : 'HWTSim2_heatout_T',
        'T_mean_hwt': 'HWTSim2_Tmean',  # Closest match is HWTSim0_Tmean
        'hwt_mass': None,    # Closest match is HWTSim1_Tmean
        'top_layer_Tank1': 'HWTSim1_sensor2_T',  # Closest match (as no direct match found),
        'tes2_heat_out2_F': 'HotWaterTankSim-2.HotWaterTank_0-heat_out2.F',  # Closest match (as no direct match found)
        'tes2_heat_out2_T' : 'HotWaterTankSim-2.HotWaterTank_0-heat_out2.T',
        'tes2_hp_out_T': 'HWTSim2_hp_out_T',
        'T_env': 'temp_air',   # Closest match is temp_air
        'hr_1.P_th_set': 'HotWaterTankSim-2.HotWaterTank_0-hr_1.P_th',  # Closest match (as no direct match found)
        'boiler_supply': 'Boilersim-0.BOILER_0-P_th',  # Closest match (as no direct match found)
        'boiler_uptime': 'ControllerSim-0.Controller_0-boiler_demand',  # Closest match (as no direct match found)
        'boiler_mdot': 'Boilersim-0.BOILER_0-mdot',     # Closest match (as no direct match found)
        'boiler_demand': 'Boilersim-0.BOILER_0-Q_Demand',    # Closest match (as no direct match found)
        'boiler_status': None,    # Closest match (as no direct match found)
        'chp_supply': 'chp_supply',         # Closest match (as no direct match found)
        'chp_uptime': 'ControllerSim-0.Controller_0-chp_uptime',  # Closest match (as no direct match found)
        'chp_mdot': 'CHP_mdot',        # Closest match (as no direct match found)
        'chp_demand': 'CHP_Q_Demand',       # Closest match (as no direct match found)
        'chp_status': None,       # Closest match (as no direct match found)
        'hp_supply': 'hp_supply',
        'hp_on_fraction': 'HP_onfraction',     # Closest match is HP_Tamb
        'hp_cond_m': 'HP_cond_m',
        'hp_out_T': 'hpout_T', #hwt0_hpout
    }  
    
    for i in ctrls_inputs.keys():
        row = '2022-01-02 02:30:00'
        if column_match[i]:
            ctrls_inputs[i] = df.loc[row, column_match[i]]

    return ctrls_inputs


@pytest.fixture
def obj(init_params, set_inputs):

    # params = init_params()
    # ctrls_inputs = set_inputs()

    controller_obj = Controller(init_params)
    for i in set_inputs.keys():
        setattr(controller_obj, i, set_inputs[i])
    
    return controller_obj
   

def test_script_inputassign(set_inputs):
 
    set_inputs['hp_in_F'] = 5
    assert set_inputs['hp_in_F'] == 5
    # with pytest.raises(TypeError):
    #     obj.calc_heat_supply(obj.config)

def test_obj(obj):
    
    assert type(obj) == Controller

def test_attributemod(obj):
    
    obj.chp_supply = 50
    assert obj.chp_supply == 50

#the big boys

def test_ctrlinputs(set_inputs):

    assert set_inputs['tes1_heat_out2_T'] is not None

def test_calc_heat_supply(obj):

    # with pytest.raises(TypeError):
    #     obj.calc_heat_supply(obj.config)

    obj.calc_heat_supply(obj.config)
    
    assert obj.sh_supply > 0

def test_heatsupply_zerodivision(obj):

    obj.tes1_heat_out2_T = obj.heat_rT

    obj.calc_heat_supply(obj.config)
    assert obj.sh_supply == 0

def test_heatsupply_typeerror(obj):
    
    obj.sh_out = 1
    with pytest.raises(TypeError):
        obj.calc_heat_supply(obj.config)

def test_negdemand(obj):

    obj.dhw_demand = -100

    obj.calc_heat_supply(obj.config)
    assert obj.dhw_supply == 0