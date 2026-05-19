import pytest
from des_sim.models.chp_model import CHP
from des_sim.models.EnTransformer_model import IncompleteConfigError

# --- Good params baseline ---
def make_chp_params():
    return {
        "nom_P_th": 90000,
        "op_stages": [0, 0.25, 0.5, 0.75, 1.0],
        "P_el": 50000,
        "efficiency": 0.8,
        "set_flow": 4.0,
        "heating_value": 10833.3
    }

# --- Validation Tests ---
def test_missing_all_electrical_params_raises():
    """CHP must have either P_el or elec_share defined."""
    params = make_chp_params()
    del params["P_el"]
    # No elec_share provided either
    
    with pytest.raises(IncompleteConfigError, match="At least one of 'P_el' or 'elec_share' must be provided"):
        CHP(params, warn=False)

def test_invalid_elec_share_raises():
    """elec_share must be between 0 and 1."""
    params = make_chp_params()
    del params["P_el"]
    params["elec_share"] = 1.5  # 150% electrical efficiency is impossible
    
    with pytest.raises(IncompleteConfigError, match="'elec_share' must be a number in"):
        CHP(params, warn=False)

# --- Auto-Calculation Tests ---
def test_elec_share_auto_calculation():
    """If P_el and nom_P_th are provided, elec_share should be computed automatically."""
    params = make_chp_params()
    # P_el = 50000, nom_P_th = 90000
    chp = CHP(params, warn=False)
    
    # elec_share = 50000 / 90000 = 0.5555...
    assert chp.elec_share == pytest.approx(0.55555, abs=0.0001)

# --- Physics & Step Tests ---
def test_electrical_power_generation_step():
    """P_el should dynamically match the current active thermal stage * elec_share."""
    params = make_chp_params()
    chp = CHP(params, warn=False)
    chp.step_size = 900
    chp.status = 'on'
    chp.temp_in = 60.0
    
    # Request 40,000 W of heat. 
    # Stages are [0, 22500, 45000, 67500, 90000]. 
    # Boiler logic will snap this up to 45,000 W.
    chp.Q_demand = 40000  
    
    chp.step(0)
    
    # Thermal power should be snapped to the 50% stage
    assert chp.P_th == 45000
    # Electrical power = 45000 * (50000/90000) = 25000 W
    assert chp.P_el == 25000

def test_electrical_power_is_zero_when_off():
    """When the CHP is off, no electricity should be produced."""
    params = make_chp_params()
    chp = CHP(params, warn=False)
    chp.step_size = 900
    chp.temp_in = 60.0
    chp.Q_demand = 90000
    chp.status = 'off'
    
    chp.step(0)
    
    assert chp.P_th == 0
    assert chp.P_el == 0