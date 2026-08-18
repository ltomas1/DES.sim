import pytest
from des_sim.models.pv_model import PV
import pandas as pd
from unittest.mock import patch


# --- Good params baseline ---
def make_valid_params(out_dir="unit_testing/dummy_path"):
    """Returns a valid param dict you can modify per test."""
    return {
        "calc_mode": "simple",
        "nom_power": 70000,
        "coordinates": [49.1, 8.5, "Stutensee", 110, "Etc/GMT-1"],
        "op_year": 2022,
        "op_mode": "standalone",
        "sim_start": "2022-01-01 00:00:00",
        "output_dir": str(out_dir),
        "pv_arrays": [
            {"tilt": 30, "azimuth": 281},
            {"tilt": 30, "azimuth": 101}
        ]
    }


# --- validate_params tests ---

def test_valid_params_pass():
    """Good params should not raise any error."""
    params = make_valid_params()
    pv = PV.__new__(PV)  # create instance without running __init__
    pv.validate_params(params)  # should not raise


def test_missing_calc_mode_raises():
    """Removing a required param should raise ValueError."""
    params = make_valid_params()
    del params["calc_mode"]
    pv = PV.__new__(PV)
    with pytest.raises(ValueError, match="missing required parameter"):
        pv.validate_params(params)


def test_missing_nom_power_raises():
    params = make_valid_params()
    del params["nom_power"]
    pv = PV.__new__(PV)
    with pytest.raises(ValueError, match="missing required parameter"):
        pv.validate_params(params)


def test_negative_nom_power_raises():
    """Negative power should fail validation."""
    params = make_valid_params()
    params["nom_power"] = -100
    pv = PV.__new__(PV)
    with pytest.raises(ValueError):
        pv.validate_params(params)


def test_invalid_calc_mode_raises():
    """Unsupported calc_mode should fail."""
    params = make_valid_params()
    params["calc_mode"] = "detailed"
    pv = PV.__new__(PV)
    with pytest.raises(ValueError, match="unsupported"):
        pv.validate_params(params)


def test_bad_coordinates_format_raises():
    """Coordinates with wrong structure should fail."""
    params = make_valid_params()
    params["coordinates"] = [49.1, 8.5]  # missing name, altitude, timezone
    pv = PV.__new__(PV)
    with pytest.raises(ValueError, match="coordinates"):
        pv.validate_params(params)


def test_op_year_mismatch_with_sim_start():
    """op_year must match the year in sim_start."""
    params = make_valid_params()
    params["op_year"] = 2023
    params["sim_start"] = "2022-01-01 00:00:00"
    pv = PV.__new__(PV)
    with pytest.raises(ValueError, match="op_year must match"):
        pv.validate_params(params)


def test_invalid_pv_arrays_missing_keys():
    """pv_arrays dicts must have tilt and azimuth."""
    params = make_valid_params()
    params["pv_arrays"] = [{"tilt": 30}]  # missing azimuth
    pv = PV.__new__(PV)
    with pytest.raises(ValueError, match="pv_arrays"):
        pv.validate_params(params)

@patch("des_sim.models.pv_model.fetch_pvgis")
def test_pv_simulation_runs_with_pvgis(mock_fetch, tmp_path):
    """Full simulation mocked to run instantly without internet."""
    dates = pd.date_range("2022-01-01", periods=3, freq="15min", tz="UTC")
    fake_df = pd.DataFrame({
        "poa_global": [0.0, 800.0, 0.0], "poa_direct": [0.0, 600.0, 0.0],
        "poa_diffuse": [0.0, 200.0, 0.0], "temp_air": [9.0, 15.0, 9.0],
        "wind_speed": [2.6, 3.2, 2.6]
    }, index=dates)

    # Return a tuple of exactly 1 DataFrame
    mock_fetch.return_value = (fake_df,)

    params = make_valid_params(out_dir=tmp_path)
    # FORCE the params to have exactly 1 array so it matches the mock!
    params["pv_arrays"] = [{"tilt": 30, "azimuth": 180}]
    
    pv = PV(params)
    result_path = pv.sim()
    
    df = pd.read_csv(result_path)
    assert len(df) > 0
    mock_fetch.assert_called_once()

@patch("des_sim.models.pv_model.fetch_pvgis")
def test_pv_multi_array_matches_single_array_count(mock_fetch, tmp_path):
    """Two arrays should produce the same number of rows as one array, instantly."""
    dates = pd.date_range("2022-01-01", periods=3, freq="15min", tz="UTC")
    fake_df = pd.DataFrame({
        "poa_global": [0.0, 800.0, 0.0], "poa_direct": [0.0, 600.0, 0.0],
        "poa_diffuse": [0.0, 200.0, 0.0], "temp_air": [9.0, 15.0, 9.0],
        "wind_speed": [2.6, 3.2, 2.6]
    }, index=dates)

    single_dir = tmp_path / "single"
    single_dir.mkdir()
    multi_dir = tmp_path / "multi"
    multi_dir.mkdir()
    
    single = make_valid_params(out_dir=single_dir)
    single["pv_arrays"] = [{"tilt": 30, "azimuth": 180}]
    
    multi = make_valid_params(out_dir=multi_dir)
    multi["pv_arrays"] = [{"tilt": 30, "azimuth": 180}, {"tilt": 30, "azimuth": 90}]
    
    # Run Single (Mock returns tuple of 1 DataFrame)
    mock_fetch.return_value = (fake_df,)
    pv_single = PV(single)
    df_single = pd.read_csv(pv_single.sim())
    
    # Run Multi (Mock returns tuple of 2 DataFrames)
    mock_fetch.return_value = (fake_df, fake_df)
    pv_multi = PV(multi)
    df_multi = pd.read_csv(pv_multi.sim())
    
    assert len(df_single) == len(df_multi)
    assert mock_fetch.call_count == 2

def test_pv_simulation_with_local_csv(tmp_path):
    """Providing a local weather CSV should bypass PVGIS and use local data."""
    # Create a fake weather CSV using your exact data structure
    fake_csv_path = tmp_path / "fake_weather.csv"
    fake_csv_path.write_text(
        "Time;Air temperature (°C);Wind speed (m/s);Global horizontal irradiance (W/m²);Direct normal irradiance (W/m²);Horizontal infrared radiation (W/m²)\n"
        "01.01. 00:00;2.1;6.2;0;0;253\n"
        "01.01. 01:00;-4;2;0;0;246\n"
        "01.01. 13:00;0;2.6;123;220;283\n",  # Added a daylight hour so power > 0
        encoding="cp1252"
    )
    
    # Setup params to point to this fake CSV
    params = make_valid_params(out_dir=tmp_path)
    params["irradiation_data"] = str(fake_csv_path)
    
    # Run the model
    pv = PV(params)
    result_path = pv.sim()
    
    # Verify it ran and produced output
    import pandas as pd
    df = pd.read_csv(result_path)
    
    assert "Power[w]" in df.columns
    assert len(df) > 0
    assert (df["Power[w]"] >= 0).all()