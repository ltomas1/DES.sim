import pytest
from des_sim.models.controller_model import Controller, IncompleteConfigError
from mosaik_components.heatpump.hotwatertank.hotwatertank import HotWaterTank
from des_sim.models.hotwatertank_mosaik import HotWaterTankSimulator

# --- Good params baseline ---
def make_controller_params(config="4-pipe"):
    return {
        "operation_mode": "heating",
        "control_strategy": "1",
        "supply_config": config,
        "heating_curve": "floor_high_insulation",
        "T_dhn_sp": 67,
        "sh_out": "tank1.heat_out2",
        "dhw_out": "tank2.heat_out",
        "sh_ret": "tank0.heat_in",
        "dhw_ret": "tank2.heat_in",
        "supply_conn": "tank2.heat_out2",
        "return_conn": "tank0.heat_in",
        "gens": ["hp", "chp", "boiler"],
        "NumberofTanks": 3,
        "TankbalanceSetup": ["tank0.heat_out:tank1.hp_out", "tank1.heat_out:tank2.hp_out"],
        "logic": {
            "chp": {
                "turn_on": {"tank": "tank2", "layer": "sensor_2", "turn_on_temp": 65},
                "turn_off": {"tank": "tank2", "layer": "sensor_2", "turn_off_temp": 75}
            },
            "hp": {
                "turn_on": {"tank": "tank1", "layer": "sensor_2", "turn_on_temp": 43},
                "turn_off": {"tank": "tank1", "layer": "sensor_2", "turn_off_temp": 65},
                "add_conditions": {"turn_on": {"battery_full": ["==", "True"]}}
            },
            "boiler": {
                "turn_on": {"tank": "tank2", "layer": "sensor_2", "turn_on_temp": 64}
            }
        },
        "tank": {
            "height": 2500,
            "volume": 20000,
            "n_layers": 3,
            "n_sensors": 3,
            "connections": {
                "heat_in": {"pos": 150},
                "heat_out": {"pos": 2350},
                "chp_in": {"pos": 2300},
                "chp_out": {"pos": 50},
                "hp_in": {"pos": 2200},
                "hp_out": {"pos": 100},
                "boiler_in": {"pos": 2400},
                "boiler_out": {"pos": 120},
                "heat_out2": {"pos": 2400},
                "heat_in2": {"pos": 200}
            },
            "heating_rods": {
                "hr_1": {
                    "mode": "on",
                    "pos": 2200,
                    "P_th_stages": [0, 500, 1000, 2000, 10000],
                    "T_max": 67,
                    "eta": 1
                }
            }
        }
    }



def make_controller(config="4-pipe", **overrides):
    """Build a controller with sensible runtime defaults."""
    ctrl = Controller(make_controller_params(config), warn=False)
    ctrl.step_size = 900
    ctrl.T_amb = 10.0
    ctrl.HP_P_Required = 0.0
    ctrl.sh_demand = 0.0
    ctrl.dhw_demand = 0.0
    ctrl.heat_demand = 0.0
    for attr, val in overrides.items():
        setattr(ctrl, attr, val)
    return ctrl


def test_missing_gens_raises():
    """Required key 'gens' must be provided."""
    params = make_controller_params()
    del params["gens"]

    with pytest.raises(IncompleteConfigError, match="gens"):
        Controller(params, warn=False)


def test_invalid_supply_config_raises():
    """supply_config must be one of the recognized strings."""
    params = make_controller_params()
    params["supply_config"] = "5-pipe"

    with pytest.raises(IncompleteConfigError, match="supply_config"):
        Controller(params, warn=False)


def test_4pipe_missing_dhw_ret_raises():
    """4-pipe requires sh_out, dhw_out, sh_ret, and dhw_ret."""
    params = make_controller_params(config="4-pipe")
    del params["dhw_ret"]

    with pytest.raises(IncompleteConfigError, match="dhw_ret"):
        Controller(params, warn=False)


def test_2pipe_missing_T_dhn_sp_raises():
    """2-pipe requires T_dhn_sp."""
    params = make_controller_params(config="2-pipe")
    del params["T_dhn_sp"]

    with pytest.raises(IncompleteConfigError, match="T_dhn_sp"):
        Controller(params, warn=False)

def test_2pipe_energy_balance_steady_state_multistep():
    """
    2-pipe: single combined supply/return loop to a district heating network.
    Uses heat_demand (total) and a fixed supply setpoint T_dhn_sp.

    Per-step invariant (no ideal heater):
        fhot * cp * (sup_T - ret_T) ≈ heat_demand_W

    Cumulative:
        sum(heat_supply * step_size) ≈ heat_demand_W * N * step_size
    """
    ctrl = make_controller(config="2-pipe")
    CP = 4184
    N_STEPS = 50

    HEAT_DEMAND_KW = 15.0
    SUP_T_SOURCE = 80.0

    total_delivered_J = 0.0

    for step_num in range(N_STEPS):
        ctrl.heat_demand = HEAT_DEMAND_KW
        ctrl.sh_demand = 0.0
        ctrl.dhw_demand = 0.0
        ctrl.tank_connections["tank2"]["heat_out2_T"] = SUP_T_SOURCE
        ctrl.tank_temps["tank1"]["sensor_2"] = 70.0
        ctrl.tank_temps["tank2"]["sensor_2"] = 80.0

        ctrl.step(step_num * ctrl.step_size)

        # --- Energy balance ---
        fhot = -ctrl.tank_connections["tank2"]["heat_out2_F"]
        ret_T = ctrl.tank_connections["tank0"]["heat_in_T"]
        energy_carried = fhot * CP * (SUP_T_SOURCE - ret_T)

        assert ctrl.IdealHrodsum == 0, f"step {step_num}: ideal heater fired"
        assert energy_carried == pytest.approx(15_000.0, rel=1e-3), (
            f"step {step_num}: energy = {energy_carried:.2f}W"
        )

        # --- 2-pipe-specific: sh_supply and dhw_supply explicitly zeroed ---
        assert ctrl.heat_supply == pytest.approx(15_000.0, abs=0.1)
        assert ctrl.sh_supply == 0, f"step {step_num}: sh_supply must be 0 in 2-pipe"
        assert ctrl.dhw_supply == 0, f"step {step_num}: dhw_supply must be 0 in 2-pipe"

        # --- Cumulative ---
        total_delivered_J += ctrl.heat_supply * ctrl.step_size

    expected_total_J = HEAT_DEMAND_KW * 1000 * N_STEPS * 900
    assert total_delivered_J == pytest.approx(expected_total_J, rel=1e-3), (
        f"cumulative delivered = {total_delivered_J:.0f}J, "
        f"expected {expected_total_J:.0f}J"
    )

def test_2pipe_dch_energy_balance_steady_state_multistep():
    """
    2-pipe-dch: 2-pipe network for SH, plus a dedicated decentralized
    electric heater for DHW (no tank involvement for DHW).

    Differences from 2-pipe:
    - Uses sh_demand (not heat_demand) for the tank-side calculation.
    - dch_power = dhw_demand / 0.98 (98% efficient electric heater for DHW).
    - sh_supply is the tank-side SH delivery; heat_supply and dhw_supply
      are NOT updated by this config (do not assert on them).

    Per-step invariants (no ideal heater):
        fhot * cp * (sup_T - ret_T) ≈ sh_demand_W
        dch_power == dhw_demand_W / 0.98

    Cumulative:
        sum(sh_supply * step_size) ≈ sh_demand_W * N * step_size
        sum(dch_power * step_size) ≈ (dhw_demand_W / 0.98) * N * step_size
    """
    ctrl = make_controller(config="2-pipe-dch")
    CP = 4184
    N_STEPS = 50

    SH_DEMAND_KW = 15.0
    DHW_DEMAND_KW = 5.0
    SUP_T_SOURCE = 80.0

    total_sh_J = 0.0
    total_dch_electric_J = 0.0

    for step_num in range(N_STEPS):
        ctrl.sh_demand = SH_DEMAND_KW
        ctrl.dhw_demand = DHW_DEMAND_KW
        ctrl.heat_demand = 0.0
        ctrl.tank_connections["tank2"]["heat_out2_T"] = SUP_T_SOURCE
        ctrl.tank_temps["tank1"]["sensor_2"] = 70.0
        ctrl.tank_temps["tank2"]["sensor_2"] = 80.0

        ctrl.step(step_num * ctrl.step_size)

        # --- Tank-side energy balance (SH circuit only) ---
        fhot = -ctrl.tank_connections["tank2"]["heat_out2_F"]
        ret_T = ctrl.tank_connections["tank0"]["heat_in_T"]
        energy_carried = fhot * CP * (SUP_T_SOURCE - ret_T)

        assert ctrl.IdealHrodsum == 0, f"step {step_num}: ideal heater fired"
        assert energy_carried == pytest.approx(15_000.0, rel=1e-3), (
            f"step {step_num}: SH energy = {energy_carried:.2f}W"
        )

        # --- 2-pipe-dch-specific ---
        assert ctrl.sh_supply == pytest.approx(15_000.0, abs=0.1)
        assert ctrl.dch_power == pytest.approx(5_000.0 / 0.98, abs=0.1)

        # --- Cumulative ---
        total_sh_J += ctrl.sh_supply * ctrl.step_size
        total_dch_electric_J += ctrl.dch_power * ctrl.step_size

    expected_sh_J = SH_DEMAND_KW * 1000 * N_STEPS * 900
    expected_dch_J = (DHW_DEMAND_KW * 1000 / 0.98) * N_STEPS * 900
    assert total_sh_J == pytest.approx(expected_sh_J, rel=1e-3)
    assert total_dch_electric_J == pytest.approx(expected_dch_J, rel=1e-3)

def test_3pipe_energy_balance_steady_state_multistep():
    """
    3-pipe: separate SH and DHW supplies (like 4-pipe), but a single
    shared return port (unlike 4-pipe's separate returns).

    Per-step invariants (no ideal heater):
        fhot_sh  * cp * (sh_T  - sh_Tret)   ≈ sh_demand_W
        fhot_dhw * cp * (dhw_T - dhw_rT)    ≈ dhw_demand_W
        F_return = fhot_sh + fhot_dhw
        T_return = (dhw_rT*fhot_dhw + sh_Tret*fhot_sh) / (fhot_sh + fhot_dhw)

    Cumulative:
        sum(sh_supply + dhw_supply) * step_size ≈ total demand
    """
    ctrl = make_controller(config="3-pipe")
    CP = 4184
    N_STEPS = 50

    SH_DEMAND_KW = 10.0
    DHW_DEMAND_KW = 5.0
    SH_T_SOURCE = 80.0
    DHW_T_SOURCE = 80.0

    total_delivered_J = 0.0

    for step_num in range(N_STEPS):
        ctrl.sh_demand = SH_DEMAND_KW
        ctrl.dhw_demand = DHW_DEMAND_KW
        ctrl.heat_demand = 0.0
        ctrl.tank_connections["tank1"]["heat_out2_T"] = SH_T_SOURCE
        ctrl.tank_connections["tank2"]["heat_out_T"] = DHW_T_SOURCE
        ctrl.tank_temps["tank1"]["sensor_2"] = 70.0
        ctrl.tank_temps["tank2"]["sensor_2"] = 80.0

        ctrl.step(step_num * ctrl.step_size)

        # --- Pull flows / temps from controller state ---
        fhot_sh = -ctrl.tank_connections["tank1"]["heat_out2_F"]
        fhot_dhw = -ctrl.tank_connections["tank2"]["heat_out_F"]
        sh_Tret = ctrl.req_shTsup - ctrl.heat_dT_sh   # heating curve return temp
        dhw_rT = ctrl.dhw_rT

        # --- Guards ---
        assert ctrl.P_hr_sh == 0, f"step {step_num}: SH ideal heater fired"
        assert ctrl.P_hr_dhw == 0, f"step {step_num}: DHW ideal heater fired"

        # --- Per-circuit energy balance ---
        sh_energy = fhot_sh * CP * (SH_T_SOURCE - sh_Tret)
        dhw_energy = fhot_dhw * CP * (DHW_T_SOURCE - dhw_rT)
        assert sh_energy == pytest.approx(10_000.0, rel=1e-3), (
            f"step {step_num}: SH energy = {sh_energy:.2f}W"
        )
        assert dhw_energy == pytest.approx(5_000.0, rel=1e-3), (
            f"step {step_num}: DHW energy = {dhw_energy:.2f}W"
        )

        # --- 3-pipe-specific: combined return port ---
        combined_F = ctrl.tank_connections["tank0"]["heat_in_F"]
        combined_T = ctrl.tank_connections["tank0"]["heat_in_T"]
        expected_combined_T = (
            (dhw_rT * fhot_dhw + sh_Tret * fhot_sh) / (fhot_sh + fhot_dhw)
        )
        assert combined_F == pytest.approx(fhot_sh + fhot_dhw, rel=1e-6), (
            f"step {step_num}: combined return flow mismatch"
        )
        assert combined_T == pytest.approx(expected_combined_T, rel=1e-3), (
            f"step {step_num}: combined return T not flow-weighted average"
        )

        # --- Cumulative ---
        total_delivered_J += (ctrl.sh_supply + ctrl.dhw_supply) * ctrl.step_size

    expected_total_J = (SH_DEMAND_KW + DHW_DEMAND_KW) * 1000 * N_STEPS * 900
    assert total_delivered_J == pytest.approx(expected_total_J, rel=1e-3), (
        f"cumulative delivered = {total_delivered_J:.0f}J, "
        f"expected {expected_total_J:.0f}J"
    )

def test_4pipe_energy_balance_steady_state_multistep():
    """
    4-pipe: separate SH and DHW supplies AND separate returns.

    Per-step invariants (no ideal heater):
        fhot_sh  * cp * (sh_T  - sh_Tret) ≈ sh_demand_W
        fhot_dhw * cp * (dhw_T - dhw_rT)  ≈ dhw_demand_W

    Cumulative:
        sum(sh_supply + dhw_supply) * step_size ≈ total demand
    """
    ctrl = make_controller(config="4-pipe")
    CP = 4184
    N_STEPS = 50

    SH_DEMAND_KW = 10.0
    DHW_DEMAND_KW = 5.0
    SH_T_SOURCE = 80.0
    DHW_T_SOURCE = 80.0

    total_delivered_J = 0.0

    for step_num in range(N_STEPS):
        ctrl.sh_demand = SH_DEMAND_KW
        ctrl.dhw_demand = DHW_DEMAND_KW
        ctrl.heat_demand = 0.0
        ctrl.tank_connections["tank1"]["heat_out2_T"] = SH_T_SOURCE
        ctrl.tank_connections["tank2"]["heat_out_T"] = DHW_T_SOURCE
        ctrl.tank_temps["tank1"]["sensor_2"] = 70.0
        ctrl.tank_temps["tank2"]["sensor_2"] = 80.0

        ctrl.step(step_num * ctrl.step_size)

        # --- SH energy balance ---
        fhot_sh = -ctrl.tank_connections["tank1"]["heat_out2_F"]
        sh_Tret = ctrl.tank_connections["tank0"]["heat_in_T"]
        sh_energy = fhot_sh * CP * (SH_T_SOURCE - sh_Tret)

        assert ctrl.P_hr_sh == 0, f"step {step_num}: SH ideal heater fired"
        assert sh_energy == pytest.approx(10_000.0, rel=1e-3), (
            f"step {step_num}: SH energy = {sh_energy:.2f}W"
        )

        # --- DHW energy balance ---
        fhot_dhw = -ctrl.tank_connections["tank2"]["heat_out_F"]
        dhw_rT = ctrl.dhw_rT
        dhw_energy = fhot_dhw * CP * (DHW_T_SOURCE - dhw_rT)

        assert ctrl.P_hr_dhw == 0, f"step {step_num}: DHW ideal heater fired"
        assert dhw_energy == pytest.approx(5_000.0, rel=1e-3), (
            f"step {step_num}: DHW energy = {dhw_energy:.2f}W"
        )

        # --- 4-pipe-specific: separate return ports ---
        assert ctrl.tank_connections["tank2"]["heat_in_F"] == pytest.approx(
            fhot_dhw, rel=1e-6
        ), f"step {step_num}: DHW return flow mismatch"
        assert ctrl.tank_connections["tank2"]["heat_in_T"] == pytest.approx(
            dhw_rT, rel=1e-6
        ), f"step {step_num}: DHW return temp mismatch"

        # --- Cumulative ---
        total_delivered_J += (ctrl.sh_supply + ctrl.dhw_supply) * ctrl.step_size

    expected_total_J = (SH_DEMAND_KW + DHW_DEMAND_KW) * 1000 * N_STEPS * 900
    assert total_delivered_J == pytest.approx(expected_total_J, rel=1e-3), (
        f"cumulative delivered = {total_delivered_J:.0f}J, "
        f"expected {expected_total_J:.0f}J"
    )

@pytest.mark.parametrize(
    "scenario,tank1_t,tank2_t,battery_soc,exp_hp,exp_chp,exp_boiler",
    [
        # All cold: every generator triggers turn-on by temperature.
        ("cold_all_on",       40.0, 60.0, 50.0,  "on",  "on",  "on"),
        # All hot: every generator triggers turn-off by temperature.
        ("hot_all_off",       80.0, 80.0, 50.0,  "off", "off", "off"),
        # HP-only: tank1 warm (between thresholds), battery full -> battery
        # override fires turn-on. CHP/boiler stay off because tank2 is hot.
        ("hp_warm_battery",   50.0, 80.0, 99.6,  "on",  "off", "off"),
        # HP-only: tank1 hot AND battery full. Battery override calls turn_on,
        # but turn_off runs after and wins because there is no override on
        # turn_off in the add_conditions. Final state: off.
        ("hp_hot_battery",    70.0, 80.0, 99.6,  "off", "off", "off"),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_generator_on_off_logic(
    scenario, tank1_t, tank2_t, battery_soc, exp_hp, exp_chp, exp_boiler
):
    """Generators turn on/off based on tank sensor temps and additional
    conditions. Covers the canonical scenarios for each generator and the
    battery-override interaction for HP."""
    ctrl = make_controller()
    ctrl.tank_temps["tank1"]["sensor_2"] = tank1_t
    ctrl.tank_temps["tank2"]["sensor_2"] = tank2_t
    ctrl.battery_soc = battery_soc
    ctrl.sh_demand = 0.0
    ctrl.dhw_demand = 0.0
    ctrl.heat_demand = 0.0

    ctrl.step(0)

    assert ctrl.generators["hp_status"] == exp_hp, f"HP wrong in {scenario}"
    assert ctrl.generators["chp_status"] == exp_chp, f"CHP wrong in {scenario}"
    assert ctrl.generators["boiler_status"] == exp_boiler, f"boiler wrong in {scenario}"


def test_generator_hysteresis():
    """Generators maintain their state when temperature is between turn-on
    and turn-off thresholds. This catches a class of refactor bugs where
    someone replaces the turn-on/turn-off pair with a single threshold."""
    ctrl = make_controller()
    ctrl.sh_demand = 0.0
    ctrl.dhw_demand = 0.0
    ctrl.heat_demand = 0.0
    ctrl.battery_soc = 50.0  # battery not full, so HP follows temperature only
    ctrl.tank_temps["tank1"]["sensor_2"] = 70.0  # HP off the whole time

    # Step 1: tank2 cold -> CHP turns on (< 65)
    ctrl.tank_temps["tank2"]["sensor_2"] = 60.0
    ctrl.step(0)
    assert ctrl.generators["chp_status"] == "on"

    # Step 2: tank2 warm (between turn_on=65 and turn_off=75) -> CHP stays on
    ctrl.tank_temps["tank2"]["sensor_2"] = 70.0
    ctrl.sh_demand = 0.0; ctrl.dhw_demand = 0.0; ctrl.heat_demand = 0.0
    ctrl.step(900)
    assert ctrl.generators["chp_status"] == "on", "CHP should hold ON"

    # Step 3: tank2 hot -> CHP turns off (>= 75)
    ctrl.tank_temps["tank2"]["sensor_2"] = 80.0
    ctrl.sh_demand = 0.0; ctrl.dhw_demand = 0.0; ctrl.heat_demand = 0.0
    ctrl.step(1800)
    assert ctrl.generators["chp_status"] == "off"

    # Step 4: tank2 back to warm -> CHP stays off
    ctrl.tank_temps["tank2"]["sensor_2"] = 70.0
    ctrl.sh_demand = 0.0; ctrl.dhw_demand = 0.0; ctrl.heat_demand = 0.0
    ctrl.step(2700)
    assert ctrl.generators["chp_status"] == "off", "CHP should hold OFF"

def test_3pipe_two_hop_cascade_balancer():
    """3-pipe with DHW demand creates a deficit at tank2 (the DHW return
    goes back to tank0, not tank2). The cascade chain
    tank0.heat_out -> tank1.hp_out -> tank2.hp_out must move flow through
    tank1 to satisfy tank2's deficit.

    This is the test that actually exercises _deficit_reachable; with a
    one-hop scenario the graph walk is never needed."""
    ctrl = make_controller(config="3-pipe")
    ctrl.sh_demand = 0.0
    ctrl.dhw_demand = 50.0       # creates large deficit at tank2
    ctrl.heat_demand = 0.0
    ctrl.tank_connections["tank1"]["heat_out2_T"] = 80.0
    ctrl.tank_connections["tank2"]["heat_out_T"] = 80.0
    ctrl.tank_temps["tank1"]["sensor_2"] = 70.0
    ctrl.tank_temps["tank2"]["sensor_2"] = 80.0

    ctrl.step(0)

    # Hop 1: tank0 sends water out through heat_out (donor port for link 1)
    hop1_flow = -ctrl.tank_connections["tank0"]["heat_out_F"]
    assert hop1_flow > 0, "Hop 1 failed: tank0 did not push flow to tank1"

    # Hop 2: tank1 forwards through heat_out (donor port for link 2).
    # This is the actual two-hop test — proves flow really cascaded
    # through the middle tank rather than tank0 magically supplying tank2.
    hop2_flow = -ctrl.tank_connections["tank1"]["heat_out_F"]
    assert hop2_flow > 0, "Hop 2 failed: tank1 did not forward flow to tank2"

    # Conservation through the chain: both hops carry the same flow.
    assert hop1_flow == pytest.approx(hop2_flow, rel=1e-6)

    # Strict mass balance per tank (controller already enforces > 1e-5;
    # we check tighter to catch silent drift).
    for tank in ctrl.tanks:
        netflow = sum(
            flow for port, flow in ctrl.tank_connections[tank].items()
            if port.endswith("_F")
        )
        assert netflow == pytest.approx(0.0, abs=1e-5), (
            f"Mass balance failed in {tank}: netflow={netflow}"
        )

#---------------------- Controller plus hot water tank substep counter tests ----------------------

def _make_tank_params():
    """Minimal tank params for the substep-counter test."""
    return {
        "height": 2500,        # mm
        "volume": 20000,       # L  -> layer volume = 6666.67 L
        "T_env": 20.0,
        "htc_walls": 0.28,
        "htc_layers": 0.897,
        "n_layers": 3,
        "n_sensors": 3,
        "connections": {
            "heat_in":  {"pos": 150},   # bottom layer
            "heat_out": {"pos": 2350},  # top layer
        },
        "heating_rods": {
            "hr_1": {
                "mode": "on",
                "pos": 2200,
                "P_th_stages": [0, 500, 1000, 2000, 10000],
                "T_max": 67,
                "eta": 1,
            },
        },
    }


def _fresh_tank():
    init_vals = {
        "layers": {"T": [40.0, 30.0, 20.0]}, 
        "hr_1": {"P_el": 0, "P_th_set": 0},
    }
    return HotWaterTank(_make_tank_params(), init_vals=init_vals)


@pytest.mark.parametrize(
    "flow_lps,expected_n",
    [
        # Layer volume = 20000/3 ≈ 6666.67 L
        # Threshold F (at step_size=900s) = 6666.67/900 ≈ 7.407 L/s
        (0.0,  1),   # no flow: no substeps
        (1.0,  1),   # 900 L per step, well under 6667 L
        (7.0,  1),   # 6300 L per step, just under
        (10.0, 2),   # 9000 L per step,  9000 // 6667 + remainder = 2
        (20.0, 3),   # 18000 L per step, 18000 // 6667 + remainder = 3
        (30.0, 5),   # 27000 L per step, 27000 // 6667 + remainder = 5
    ],
)
def test_compute_n_substeps(flow_lps, expected_n):
    """Substep counter returns the right number of substeps for various
    flow rates. Mirrors the CFL check inside HotWaterTank.step()."""
    sim = HotWaterTankSimulator()
    tank = _fresh_tank()

    if flow_lps > 0:
        tank.connections["heat_in"].T = 60.0       # set T before F when F>0
        tank.connections["heat_in"].F = flow_lps
        tank.connections["heat_out"].F = -flow_lps

    n = sim._compute_n_substeps(tank, step_size=900)
    assert n == expected_n, (
        f"flow={flow_lps} L/s: expected {expected_n} substeps, got {n}"
    )


def test_compute_n_substeps_cleans_up_layer_massflows():
    """_compute_n_substeps temporarily adds massflows to layers as part of
    its CFL check. It must leave layer.massflows empty afterwards, otherwise
    the next call to tank.step() sees stale state."""
    sim = HotWaterTankSimulator()
    tank = _fresh_tank()
    tank.connections["heat_in"].T = 60.0
    tank.connections["heat_in"].F = 5.0
    tank.connections["heat_out"].F = -5.0

    sim._compute_n_substeps(tank, step_size=900)

    for idx, layer in enumerate(tank.layers):
        assert layer.massflows == [], (
            f"layer {idx} still has massflows after _compute_n_substeps: "
            f"{layer.massflows}"
        )

def test_step_model_T_buffer_captures_every_substep():
    """After _step_model runs with substepping, each outflow connection's
    _T_buffer should contain exactly N entries — one per substep. If the
    first substep is invoked with adapted_step_size_mode=False, it clears
    the buffer but does NOT append, so the average is over N-1 substeps
    instead of N and the controller sees a biased outflow temperature."""
    sim = HotWaterTankSimulator()
    tank = _fresh_tank()

    # 20 L/s × 900 s = 18000 L > layer volume (6666.67 L) -> n_substeps = 3
    tank.connections["heat_in"].T = 60.0
    tank.connections["heat_in"].F = 20.0
    tank.connections["heat_out"].F = -20.0

    expected_n = 3
    assert sim._compute_n_substeps(tank, step_size=900) == expected_n, (
        "precondition: this flow should require 3 substeps"
    )

    sim._step_model(tank, step_size=900)

    actual = len(tank.connections["heat_out"]._T_buffer)
    assert actual == expected_n, (
        f"Outflow _T_buffer has {actual} entries after {expected_n} substeps. "
        f"Expected {expected_n} (one per substep). If the count is one less "
        f"than expected, the first substep is being called with "
        f"adapted_step_size_mode=False, which clears _T_buffer but skips "
        f"the append at the end."
    )

def test_controller_tanks_coupled_energy_balance_multistep():
    """Controller coupled with 3 HotWaterTanks running 30 steps in 4-pipe
    config, with no external heat input (heating rods off).

    System-level energy conservation (no generator input, no heating-rod
    activity):

        ΔU_tanks = E_ideal_heater − E_demanded − E_loss_to_env

    Where:
      - ΔU_tanks  : sum across tanks/layers of m * cp * (T_final − T_initial)
      - E_demanded: sum of (sh_demand + dhw_demand) * step_size over steps
      - E_ideal_heater: sum of ctrl.IdealHrodsum * step_size — virtual heat
        the controller credits when the tank can't supply enough
      - E_loss_to_env: sum across tanks/layers/steps of
        (T_layer − T_env) * outer_surface * htc_walls * step_size

    If this equation closes, the controller's bookkeeping is consistent
    with the tank's actual physics across the substep boundary.
    """
    sim = HotWaterTankSimulator()

    params = make_controller_params(config="4-pipe")
    ctrl = Controller(params, warn=False)
    ctrl.step_size = 900
    ctrl.T_amb = 10.0
    ctrl.HP_P_Required = 0.0

    # HotWaterTank needs geometry/loss params that aren't in the controller's
    # tank dict — pull them in from the production config defaults.
    tank_params = {
        **params["tank"],
        "height": 2500,
        "T_env": 20.0,
        "htc_walls": 0.28,
        "htc_layers": 0.897,
    }

    # Stable thermal gradient: cold at bottom, hot at top. Top of tank1 and
    # tank2 (80°C) are the SH and DHW sources respectively.
    init_temps = [
        [30.0, 30.0, 30.0],  # tank0: cool buffer for returns
        [60.0, 70.0, 80.0],  # tank1: SH source at top
        [50.0, 60.0, 70.0],  # tank2: DHW source at top
    ]
    tanks = []
    for T in init_temps:
        iv = {"layers": {"T": T}, "hr_1": {"P_el": 0, "P_th_set": 0}}
        tanks.append(HotWaterTank(tank_params, init_vals=iv))

    CP = 4184
    RHO = 1.0  # kg/L
    N_STEPS = 60
    SH_DEMAND_KW = 5.0
    DHW_DEMAND_KW = 5.0

    def sync_tank_to_controller():
        """Push tank state (sensors, outflow temps) into the controller's
        view. This is what mosaik does between simulator steps."""
        for i, tank in enumerate(tanks):
            tname = f"tank{i}"
            # Tank sensors are sensor_00, sensor_01, ...; controller uses
            # sensor_0, sensor_1, ...
            for j in range(params["tank"]["n_sensors"]):
                ctrl.tank_temps[tname][f"sensor_{j}"] = (
                    tank.sensors[f"sensor_{j:02d}"].T
                )
            for pname, conn in tank.connections.items():
                if conn.F <= 0:
                    ctrl.tank_connections[tname][f"{pname}_T"] = conn.T

    def sync_controller_to_tank():
        """Push controller decisions (flows, inflow temps) back to tanks."""
        for i, tank in enumerate(tanks):
            tname = f"tank{i}"
            for pname, conn in tank.connections.items():
                conn.F = ctrl.tank_connections[tname][f"{pname}_F"]
                if conn.F > 0:
                    conn.T = ctrl.tank_connections[tname][f"{pname}_T"]

    def total_internal_energy():
        return sum(
            layer.volume * RHO * CP * layer.T
            for tank in tanks for layer in tank.layers
        )

    def step_heat_loss():
        """Heat lost to env this step, using pre-step layer temperatures.
        Matches the tank's own internal heatflow-to-env calculation."""
        return sum(
            (layer.T - tank.T_env) * layer.outer_surface * tank.htc_walls
            * ctrl.step_size
            for tank in tanks for layer in tank.layers
        )

    U_initial = total_internal_energy()
    total_demanded_J = 0.0
    total_delivered_J = 0.0
    total_ideal_heater_J = 0.0
    total_loss_J = 0.0
    ideal_heater_fired = False

    for step_num in range(N_STEPS):
        sync_tank_to_controller()

        ctrl.sh_demand = SH_DEMAND_KW
        ctrl.dhw_demand = DHW_DEMAND_KW
        ctrl.heat_demand = 0.0

        ctrl.step(step_num * ctrl.step_size)

        total_delivered_J += (ctrl.sh_supply + ctrl.dhw_supply) * ctrl.step_size
        total_demanded_J += (SH_DEMAND_KW + DHW_DEMAND_KW) * 1000 * ctrl.step_size
        step_ideal = ctrl.IdealHrodsum * ctrl.step_size
        total_ideal_heater_J += step_ideal
        if step_ideal > 0:
            ideal_heater_fired = True

        # Heat loss is computed BEFORE tank.step() so the layer temps match
        # what the tank uses for its own internal heat-loss calculation.
        total_loss_J += step_heat_loss()

        sync_controller_to_tank()
        for tank in tanks:
            sim._step_model(tank, ctrl.step_size)

    U_final = total_internal_energy()
    delta_U = U_final - U_initial

    # ----- Check 1: controller delivered what was demanded -----
    assert total_delivered_J == pytest.approx(total_demanded_J, rel=1e-3), (
        f"delivered ({total_delivered_J:.0f} J) != "
        f"demanded ({total_demanded_J:.0f} J)"
    )

    # ----- Check 2: tanks lost energy (no input, demand is being pulled) -----
    assert delta_U < 0, f"expected tanks to lose energy; got ΔU = {delta_U:.0f} J"

    # ----- Check 3: ideal heater fired at some point -----
    # 60 steps of constant draw with no input must cool tanks enough that
    # the ideal heater kicks in. If this doesn't happen, the test scenario
    # is too gentle to actually exercise the ideal-heater accounting path.
    assert ideal_heater_fired, (
        "expected the ideal heater to fire at least once over 60 steps "
        "with no external heat input — increase demand or steps if not"
    )

    # ----- Check 4: system-level energy balance closes -----
    expected_delta_U = total_ideal_heater_J - total_demanded_J - total_loss_J
    tolerance = 0.02 * total_demanded_J  # 2% of total demand
    assert abs(delta_U - expected_delta_U) < tolerance, (
        f"Energy balance does not close:\n"
        f"  ΔU (measured from layer temps)  = {delta_U:.0f} J\n"
        f"  ΔU (expected from budget)       = {expected_delta_U:.0f} J\n"
        f"  discrepancy                     = {delta_U - expected_delta_U:.0f} J\n"
        f"  components:\n"
        f"    E_demanded total              = {total_demanded_J:.0f} J\n"
        f"    E_ideal_heater total          = {total_ideal_heater_J:.0f} J\n"
        f"    E_loss total                  = {total_loss_J:.0f} J\n"
        f"  tolerance (2% of demand)        = {tolerance:.0f} J"
    )

def test_controller_tanks_boiler_coupled_energy_balance():
    """Coupled controller + 3 tanks + gas boiler in 4-pipe config, 60 steps.

    Tank2 starts at moderate temperature (top at 70°C, just 5°C above the
    boiler's 64°C turn-on threshold). DHW + SH demand cool the tanks until
    tank2 drops past 64°C, at which point the boiler turns on, heats tank2
    until it exceeds 69°C (turn-on + 5 default), then turns off. Cycle
    repeats.

    Energy balance:
        ΔU_tanks = E_boiler_input + E_ideal_heater - E_demanded - E_loss

    This adds a real heat source to the energy budget. If the controller's
    boiler turn-on/turn-off logic or the boiler model's flow calculation
    has a bug, the equation won't close.
    """
    from des_sim.models.boiler_model import Gboiler

    sim = HotWaterTankSimulator()

    params = make_controller_params(config="4-pipe")
    ctrl = Controller(params, warn=False)
    ctrl.step_size = 900
    ctrl.T_amb = 10.0
    ctrl.HP_P_Required = 0.0
    # See design note: this attribute is unset in __init__; in production
    # mosaik wires it from the tank model. We set it explicitly.
    ctrl.hwt_mass = 20000

    # Boiler matching the production config (200 kW gas boiler, 75°C setpoint)
    boiler = Gboiler(
        {
            "nom_P_th": 200000,
            "set_temp": 75,
            "efficiency": 0.8,
            "heating_value": 10833.3,
        },
        warn=False,
    )
    boiler.step_size = ctrl.step_size
    boiler.status = "off"
    boiler.Q_demand = 0

    tank_params = {
        **params["tank"],
        "height": 2500,
        "T_env": 20.0,
        "htc_walls": 0.28,
        "htc_layers": 0.897,
    }
    init_temps = [
        [30.0, 30.0, 30.0],   # tank0: return buffer
        [60.0, 70.0, 80.0],   # tank1: SH source at top
        [60.0, 65.0, 70.0],   # tank2: DHW source, near boiler threshold
    ]
    tanks = []
    for T in init_temps:
        iv = {"layers": {"T": T}, "hr_1": {"P_el": 0, "P_th_set": 0}}
        tanks.append(HotWaterTank(tank_params, init_vals=iv))

    CP = 4184
    RHO = 1.0
    N_STEPS = 1000
    SH_DEMAND_KW = 5.0
    DHW_DEMAND_KW = 5.0

    def sync_tank_to_controller():
        for i, tank in enumerate(tanks):
            tname = f"tank{i}"
            for j in range(params["tank"]["n_sensors"]):
                ctrl.tank_temps[tname][f"sensor_{j}"] = (
                    tank.sensors[f"sensor_{j:02d}"].T
                )
            for pname, conn in tank.connections.items():
                if conn.F <= 0:
                    ctrl.tank_connections[tname][f"{pname}_T"] = conn.T

    def sync_controller_to_tank():
        for i, tank in enumerate(tanks):
            tname = f"tank{i}"
            for pname, conn in tank.connections.items():
                conn.F = ctrl.tank_connections[tname][f"{pname}_F"]
                if conn.F > 0:
                    conn.T = ctrl.tank_connections[tname][f"{pname}_T"]

    def sync_boiler_to_tank2():
        """Push boiler flows to tank2's boiler_in/boiler_out ports.
        MUST run after sync_controller_to_tank, since that wipes all
        connection F values back to the controller's view (which has
        boiler ports at 0)."""
        if boiler.mdot is not None and boiler.mdot > 0:
            # Set T before F when F is becoming positive, so the connection
            # picks its corresponding_layer by temperature match (not position).
            tanks[2].connections["boiler_in"].T = boiler.temp_out
            tanks[2].connections["boiler_in"].F = boiler.mdot
            tanks[2].connections["boiler_out"].F = boiler.mdot_neg
        else:
            tanks[2].connections["boiler_in"].F = 0
            tanks[2].connections["boiler_out"].F = 0

    def total_internal_energy():
        return sum(
            layer.volume * RHO * CP * layer.T
            for tank in tanks for layer in tank.layers
        )

    def step_heat_loss():
        return sum(
            (layer.T - tank.T_env) * layer.outer_surface * tank.htc_walls
            * ctrl.step_size
            for tank in tanks for layer in tank.layers
        )

    U_initial = total_internal_energy()
    total_demanded_J = 0.0
    total_delivered_J = 0.0
    total_ideal_heater_J = 0.0
    total_boiler_input_J = 0.0
    total_loss_J = 0.0
    boiler_fired = False

    for step_num in range(N_STEPS):
        sync_tank_to_controller()

        ctrl.sh_demand = SH_DEMAND_KW
        ctrl.dhw_demand = DHW_DEMAND_KW
        ctrl.heat_demand = 0.0

        ctrl.step(step_num * ctrl.step_size)

        # Controller -> boiler (status + demand)
        boiler.status = ctrl.generators["boiler_status"]
        boiler.Q_demand = ctrl.generators["boiler_demand"]
        boiler.step_size = ctrl.step_size
        # Tank -> boiler (cold-side inlet temperature)
        boiler.temp_in = tanks[2].connections["boiler_out"].T

        boiler.step(step_num * ctrl.step_size)

        if boiler.status == "on" and boiler.P_th > 0:
            boiler_fired = True

        total_delivered_J += (ctrl.sh_supply + ctrl.dhw_supply) * ctrl.step_size
        total_demanded_J += (SH_DEMAND_KW + DHW_DEMAND_KW) * 1000 * ctrl.step_size
        total_ideal_heater_J += ctrl.IdealHrodsum * ctrl.step_size
        total_boiler_input_J += boiler.P_th * ctrl.step_size

        total_loss_J += step_heat_loss()

        sync_controller_to_tank()
        sync_boiler_to_tank2()

        for tank in tanks:
            sim._step_model(tank, ctrl.step_size)

    U_final = total_internal_energy()
    delta_U = U_final - U_initial

    # ----- Checks -----
    assert total_delivered_J == pytest.approx(total_demanded_J, rel=1e-3), (
        f"delivered != demanded: {total_delivered_J:.0f} vs {total_demanded_J:.0f}"
    )

    assert boiler_fired, (
        "boiler should have fired at least once — tank2 top should drop below "
        "64°C within 1000 steps under 5 kW DHW draw with initial top temp 70°C"
    )

    expected_delta_U = (
        total_boiler_input_J + total_ideal_heater_J
        - total_demanded_J - total_loss_J
    )
    tolerance = 0.005 * total_demanded_J
    assert abs(delta_U - expected_delta_U) < tolerance, (
        f"Energy balance does not close:\n"
        f"  ΔU (measured)            = {delta_U:.0f} J\n"
        f"  ΔU (expected)            = {expected_delta_U:.0f} J\n"
        f"  discrepancy              = {delta_U - expected_delta_U:.0f} J\n"
        f"  budget components:\n"
        f"    E_demanded             = {total_demanded_J:.0f} J\n"
        f"    E_boiler_input         = {total_boiler_input_J:.0f} J\n"
        f"    E_ideal_heater         = {total_ideal_heater_J:.0f} J\n"
        f"    E_loss                 = {total_loss_J:.0f} J\n"
        f"  tolerance (0.1% of demand) = {tolerance:.0f} J"
    )
    # ----- Budget summary (visible with pytest -s) -----
    print(f"\n{'='*55}")
    print(f"  Energy Budget Summary ({N_STEPS} steps × {ctrl.step_size}s)")
    print(f"{'='*55}")
    print(f"  ΔU tanks (measured)     : {delta_U/1e6:+.4f} MJ")
    print(f"  ΔU tanks (expected)     : {expected_delta_U/1e6:+.4f} MJ")
    print(f"  discrepancy             : {(delta_U - expected_delta_U)/1e6:+.6f} MJ")
    print(f"{'='*55}")
    print(f"  E_demanded              : {total_demanded_J/1e6:.4f} MJ")
    print(f"  E_boiler_input          : {total_boiler_input_J/1e6:.4f} MJ")
    print(f"  E_ideal_heater          : {total_ideal_heater_J/1e6:.4f} MJ")
    print(f"  E_loss                  : {total_loss_J/1e6:.4f} MJ")
    print(f"{'='*55}")