import pytest
import numpy as np
from des_sim.models.EnTransformer_model import Transformer_base, IncompleteConfigError

def make_valid_params():
    return {
        "nom_P_th": 50000,
        "efficiency": 0.9,
        "set_temp": 80.0
    }

# --- Validation Tests ---
def test_valid_params_pass():
    params = make_valid_params() 
    transformer = Transformer_base(params, warn=False)
    assert transformer.nom_P_th == 50000

def test_missing_efficiency_raises():
    params = make_valid_params()
    del params["efficiency"]
    with pytest.raises(IncompleteConfigError, match="missing required parameter"):
        Transformer_base(params, warn=False)

def test_missing_temp_and_flow_raises():
    """Must provide either set_temp or set_flow."""
    params = make_valid_params()
    del params["set_temp"]
    with pytest.raises(IncompleteConfigError, match="At least one of 'set_flow' or 'set_temp' must be defined"):
        Transformer_base(params, warn=False)

def test_missing_power_definition_raises():
    """Must provide either nom_P_th or heat_out_caps."""
    params = make_valid_params()
    del params["nom_P_th"]
    with pytest.raises(IncompleteConfigError, match="Either 'heat_out_caps' or 'nom_P_th'"):
        Transformer_base(params, warn=False)

# --- Auto-Fill Logic Tests ---
def test_auto_fill_heat_out_caps():
    """If nom_P_th and op_stages are given, heat_out_caps should be calculated."""
    params = make_valid_params()
    params["op_stages"] = [0, 0.5, 1.0]
    transformer = Transformer_base(params, warn=False)
    
    assert np.array_equal(transformer.heat_out_caps, [0, 25000, 50000])

def test_auto_fill_nom_P_th():
    """If heat_out_caps is given without nom_P_th, nom_P_th becomes the max capacity."""
    params = {
        "efficiency": 0.9,
        "set_temp": 80.0,
        "heat_out_caps": [0, 25000, 50000]
    }
    transformer = Transformer_base(params, warn=False)
    
    assert transformer.nom_P_th == 50000

# --- Physics & Step Tests ---
def test_step_with_set_temp():
    """Given a fixed output temp, the model should calculate the required mass flow and fuel."""
    params = make_valid_params()
    params["set_temp"] = 80.0
    transformer = Transformer_base(params, warn=False)
    transformer.step_size = 900  # 15 mins
    transformer.P_th = 50000     # 50kW requested
    transformer.temp_in = 60.0   # Return temp is 60C
    
    transformer.step(0)
    
    # Check mass flow: mdot = P_th / (cp * delta_T)
    # mdot = 50000 / (4187 * (80 - 60)) = 50000 / 83740 = 0.59708... kg/s
    assert transformer.mdot == pytest.approx(0.59708, abs=0.001)
    assert transformer.temp_out == 80.0
    
    # Check fuel: (P_th * hours) / (eta * heat_value)
    # fuel = (50000 * 0.25) / (0.9 * 10833.3) = 1.282...
    assert transformer.fuel == pytest.approx(1.282, abs=0.01)

def test_step_with_set_flow():
    """Given a fixed mass flow, the model should calculate the resulting output temp."""
    params = make_valid_params()
    del params["set_temp"]
    params["set_flow"] = 1.0
    transformer = Transformer_base(params, warn=False)
    transformer.step_size = 900
    transformer.P_th = 50000
    transformer.temp_in = 60.0
    
    transformer.step(0)
    
    # Check output temp: temp_out = (P_th / (mdot * cp)) + temp_in
    # temp_out = (50000 / (1.0 * 4187)) + 60 = 11.94... + 60 = 71.941...
    assert transformer.temp_out == pytest.approx(71.941, abs=0.001)
    assert transformer.mdot == 1.0

def test_reverse_flow_prevention():
    """If temp_in is higher than set_temp, mass flow should clip to 0 instead of going negative."""
    params = make_valid_params()
    params["set_temp"] = 80.0
    transformer = Transformer_base(params, warn=False)
    transformer.step_size = 900
    transformer.P_th = 50000
    transformer.temp_in = 90.0
    
    transformer.step(0)
    
    # Mass flow equation would yield a negative number, but max(0, mdot) should catch it
    assert transformer.mdot == 0.0