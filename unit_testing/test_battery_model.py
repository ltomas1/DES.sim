import pytest
from des_sim.models.battery_model import Battery

def make_valid_params():
    return {
        "nom_capacity": 65000,
        "charge_eff": 0.93,
        "max_charge_power": 25000
    }

def test_valid_params_pass():
    params = make_valid_params()
    bat = Battery.__new__(Battery)
    bat.validate_params(params)

def test_missing_capacity_raises():
    params = make_valid_params()
    del params["nom_capacity"]
    bat = Battery.__new__(Battery)
    with pytest.raises(ValueError, match="missing required parameter"):
        bat.validate_params(params)

def test_invalid_efficiency_raises():
    params = make_valid_params()
    params["charge_eff"] = 1.5  # Over 100%
    bat = Battery.__new__(Battery)
    with pytest.raises(ValueError):
        bat.validate_params(params)

def test_default_discharge_params():
    """If discharge params are omitted, they should mirror charge params."""
    params = make_valid_params()
    bat = Battery(params)
    
    assert bat.discharge_eff == bat.charge_eff
    assert bat.max_discharge_power == bat.max_charge_power

def test_normal_charge_step():
    """Charging at 10,000W for 15 mins (0.25h) with 93% efficiency on 65kWh battery."""
    bat = Battery(make_valid_params())
    bat.step_size = 900  # 15 mins
    bat.P_el_in = 10000

    bat.step(0)

    # Energy in: 10000W * 0.25h * 0.93 = 2325 Wh
    # SOC change: (2325 / 65000) * 100 = 3.57692...
    assert bat.soc == pytest.approx(3.57692, abs=0.001)
    assert bat.P_el_in == 10000  # Power shouldn't be clipped

def test_normal_discharge_step():
    """Discharging at 10,000W for 15 mins (0.25h) on a full 65kWh battery."""
    bat = Battery(make_valid_params())
    bat.step_size = 900
    bat.soc = 100.0
    bat.P_el_out = 10000

    bat.step(0)

    # Energy out: 10000W * 0.25h / 0.93 efficiency = 2688.17 Wh drawn from battery
    # SOC change: (2688.17 / 65000) * 100 = 4.1356...
    # New SOC: 100 - 4.1356 = 95.864...
    assert bat.soc == pytest.approx(95.864, abs=0.001)
    assert bat.P_el_out == 10000

def test_charge_power_limit_clipping():
    """P_el_in exceeding max_charge_power (25,000W) should be hard-capped for the 15 min step."""
    bat = Battery(make_valid_params())
    bat.step_size = 900
    bat.P_el_in = 35000  # Exceeds the 25,000 limit

    bat.step(0)

    assert bat.P_el_in == 25000 # Clipped!
    # Energy in: 25000W * 0.25h * 0.93 = 5812.5 Wh
    # SOC change: (5812.5 / 65000) * 100 = 8.94230...
    assert bat.soc == pytest.approx(8.94230, abs=0.001)

def test_discharge_power_limit_clipping():
    """P_el_out exceeding max_discharge_power (25,000W) should be hard-capped."""
    bat = Battery(make_valid_params())
    bat.step_size = 900
    bat.soc = 100.0
    bat.P_el_out = 50000  # Exceeds the 25k limit

    bat.step(0)

    assert bat.P_el_out == 25000  # Clipped!
    # Energy out: 25000W * 0.25h / 0.93 = 6720.43 Wh
    # SOC change: (6720.43 / 65000) * 100 = 10.339...
    assert bat.soc == pytest.approx(89.66, abs=0.01)

def test_soc_overcharge_recalculation():
    """Charging past 100% in 15 mins should clip SOC to 100 and reduce P_el_in."""
    bat = Battery(make_valid_params())
    bat.step_size = 900
    bat.soc = 95.0
    bat.P_el_in = 25000  # Would push SOC past 100%
    
    # We need 5% of 65,000Wh = 3250 Wh of stored energy to reach 100% SOC.
    # Factoring 0.93 efficiency, we must pull 3250 / 0.93 = 3494.62 Wh from the sources.
    # To get 3494.62 Wh in just 15 mins (0.25h), power must be 4x higher: 3494.62 / 0.25 = 13978.49 W
    bat.step(0)

    assert bat.soc == 100.0
    assert bat.P_el_in == pytest.approx(13978.49, abs=0.01)

def test_soc_over_discharge_recalculation():
    """Discharging below 0% in 15 mins should clip SOC to 0 and reduce P_el_out."""
    bat = Battery(make_valid_params())
    bat.step_size = 900
    bat.soc = 5.0
    bat.P_el_out = 25000  # Would completely drain the battery and go negative
    
    # We only have 5% of 65,000Wh = 3250 Wh of stored energy to give.
    # Factoring 0.93 discharge efficiency, we can provide 3250 * 0.93 = 3022.5 Wh to the heat pump.
    # To output 3022.5 Wh in just 15 mins (0.25h), power must be 4x higher: 3022.5 / 0.25 = 12090.0 W
    bat.step(0)

    assert bat.soc == 0.0
    assert bat.P_el_out == pytest.approx(12090.0, abs=0.1)

def test_standby_step():
    """If no power is flowing, SOC remains exactly the same."""
    bat = Battery(make_valid_params())
    bat.step_size = 900
    bat.soc = 50.0
    # Intentionally leaving P_el_in and P_el_out as None

    bat.step(0)

    assert bat.soc == 50.0