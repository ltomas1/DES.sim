import pytest
from des_sim.models.boiler_model import Gboiler
from des_sim.models.EnTransformer_model import IncompleteConfigError

# --- Good params baseline ---
def make_boiler_params():
    return {
        "efficiency": 0.9,
        "set_temp": 80.0,
        "heat_out_caps": [0, 50000, 100000],  # 0kW, 50kW, 100kW stages
    }

# ---  Validation Tests ---
def test_missing_startup_limit_raises():
    """If coeffs are provided, startup_limit MUST be provided."""
    params = make_boiler_params()
    params["startup_coeff"] = [10.0, 5.0]
    # No startup_limit provided
    
    with pytest.raises(IncompleteConfigError, match="'startup_limit' is required"):
        Gboiler(params, warn=False)

# --- Physics & Step Tests ---
def test_stage_selection_rounds_up():
    """Demand of 30kW should snap to the 50kW stage."""
    boiler = Gboiler(make_boiler_params(), warn=False)
    boiler.step_size = 900
    boiler.status = 'on'
    boiler.temp_in = 60.0
    boiler.Q_demand = 30000  # 30kW demand
    
    boiler.step(0)
    
    assert boiler.P_th == 50000  # Snapped to 50kW stage

def test_stage_selection_max_cap():
    """Demand of 150kW should cap at the max 100kW stage."""
    boiler = Gboiler(make_boiler_params(), warn=False)
    boiler.step_size = 900
    boiler.status = 'on'
    boiler.temp_in = 60.0
    boiler.Q_demand = 150000  # 150kW demand
    
    boiler.step(0)
    
    assert boiler.P_th == 100000  # Capped at max stage

def test_polynomial_startup_math():
    """Tests if the polynomial correctly calculates P_th and eta during startup."""
    params = make_boiler_params()
    # P_th(kW) = 10.0 + 5.0 * uptime(min)
    params["startup_coeff"] = [10.0, 5.0]
    # eta = 0.5 + 0.1 * uptime(min)
    params["startup_eta_coeff"] = [0.5, 0.1]
    params["startup_limit"] = 10.0  # 10 minutes
    
    boiler = Gboiler(params, warn=False)
    boiler.step_size = 60  # 1 minute steps so we don't trigger the 'skip' logic
    boiler.temp_in = 60.0
    boiler.Q_demand = 100000
    
    # Step 1: Turn on at time = 0
    boiler.status = 'on'
    boiler.step(0)
    assert boiler.uptime == 0.0
    # P_th = (10.0 + 5.0*0) * 1000 = 10000W
    assert boiler.P_th == 10000
    assert boiler.eta == 0.5
    
    # Step 2: Advance to time = 180 seconds (3 minutes)
    boiler.step(180)
    assert boiler.uptime == 3.0
    # P_th = (10.0 + 5.0*3) * 1000 = 25000W
    assert boiler.P_th == 25000
    # eta = 0.5 + 0.1*3 = 0.8
    assert boiler.eta == 0.8

def test_uptime_resets_on_off_status():
    """Turning the boiler off should instantly drop P_th to 0 and reset uptime."""
    boiler = Gboiler(make_boiler_params(), warn=False)
    boiler.step_size = 60
    boiler.temp_in = 60.0
    boiler.Q_demand = 50000
    
    # Turn on
    boiler.status = 'on'
    boiler.step(0)
    boiler.step(120)  # Uptime is now 2 minutes
    assert boiler.uptime == 2.0
    
    # Turn off
    boiler.status = 'off'
    boiler.step(180)
    
    assert boiler.uptime == 0.0
    assert boiler.P_th == 0

def test_startup_skip_averaging():
    """If step_size > startup_limit, it should calculate the time-averaged P_th."""
    params = make_boiler_params()
    params["startup_coeff"] = [0.0, 1.0] # Dummy coeffs, the 'skip' logic overrides this anyway
    params["startup_limit"] = 5.0  # 5 minutes
    
    boiler = Gboiler(params, warn=False)
    boiler.step_size = 900  # 15 minutes (longer than 5 min startup)
    boiler.temp_in = 60.0
    boiler.status = 'on'
    boiler.Q_demand = 100000  # Will target the 100kW stage
    
    boiler.step(0)
    # The boiler should ramp from 0 to 100kW over the first 5 minutes, then stay at 100kW for the remaining 10 minutes.
    # (0.5 * (5/60)*100000 + ((15/60 - 5/60)/60 * 100000)) / (15/60)
    # This evaluates to ~83333.33 W
    assert boiler.P_th == pytest.approx(83333.33, abs=0.1)