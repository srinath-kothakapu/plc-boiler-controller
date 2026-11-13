"""Closed-loop tests of the IEC 61131-3 program, compiled to C by MATIEC and
run against the boiler model in sim/plant.py."""
import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))
from plant import Boiler, DT

OFF, PUMP_START, RUN, FAULT = 0, 1, 2, 3


def running_boiler(**kw):
    b = Boiler(**kw)
    b.press("start")
    b.run(5)
    assert b.out.state == RUN
    return b


def test_idle_without_start_command():
    b = Boiler()
    b.run(60)
    assert b.out.state == OFF and not b.out.pump_cmd and not b.out.burner_enable


def test_startup_sequence_pump_before_burner():
    b = Boiler()
    b.press("start", 0.2)
    assert b.out.state == PUMP_START and b.out.pump_cmd
    assert not b.out.burner_enable            # no heat before flow is proven
    b.run(3)
    assert b.out.state == RUN and b.out.burner_enable


def test_reaches_setpoint_with_small_overshoot():
    b = running_boiler(setpoint=80.0)
    b.run(1500)
    temps = [r[1] for r in b.log]
    assert max(temps) < 80.0 + 5.0            # overshoot < 5 K
    assert abs(b.temp - 80.0) < 1.0           # settled within 1 K
    assert not any((b.out.alm_high, b.out.alm_noflow, b.out.alm_sensor))


def test_holds_setpoint_under_load_disturbance():
    b = running_boiler(setpoint=70.0)
    b.run(1500)
    b.p_load = 5000.0                          # process suddenly draws 5 kW
    b.run(900)
    assert abs(b.temp - 70.0) < 1.5
    assert b.out.power_pct > 20.0              # controller raised its output


def test_setpoint_is_clamped_to_90_degC():
    b = running_boiler(setpoint=150.0)         # operator typo
    b.run(2400)
    assert max(r[1] for r in b.log) < 95.0     # never reaches the trip level
    assert not b.out.alm_high


def test_pump_start_timeout_blocks_burner():
    b = Boiler(pump_broken=True)
    b.press("start", 0.2)
    b.run(5.5)
    assert b.out.alm_noflow and b.out.state == FAULT
    assert not any(r[3] for r in b.log)        # burner was never enabled


def test_pump_loss_in_run_trips_within_3_5_s():
    b = running_boiler()
    b.run(120)
    assert b.out.burner_enable
    b.pump_broken = True
    n = 0
    while not b.out.alm_noflow and n < 100:
        b.step(); n += 1
    assert b.out.alm_noflow and n * DT <= 5.0   # pump timeout 3 s + feedback delay
    assert not b.out.burner_enable and b.out.state == FAULT


def test_estop_drops_all_outputs_immediately():
    b = running_boiler()
    b.run(60)
    b.estop_ok = False
    b.step()
    assert b.out.alm_estop and b.out.state == FAULT
    assert not b.out.pump_cmd and not b.out.burner_enable


@pytest.mark.parametrize("bad", [-50.0, 250.0])
def test_sensor_open_or_short_circuit(bad):
    b = running_boiler()
    b.run(60)
    b.sensor_override = bad
    b.step()
    assert b.out.alm_sensor and b.out.state == FAULT and not b.out.burner_enable


def test_high_limit_trip_latches_and_resets_with_hysteresis():
    b = running_boiler(setpoint=80.0)
    b.contactor_welded = True                  # heater stuck on = worst case
    assert b.run(3000, until=lambda s: s.out.alm_high)
    assert b.temp < 96.0                       # tripped right at the 95 degC limit
    assert b.out.state == FAULT and not b.out.burner_enable
    assert b.out.pump_cmd                      # post-circulation to shed heat
    b.contactor_welded = False                 # electrician fixes the contactor
    b.press("reset")
    assert b.out.alm_high                      # still hot: reset refused
    assert b.run(3000, until=lambda s: s.temp < 85.0)
    assert b.out.alm_high                      # alarm is latched without reset
    b.press("reset")
    assert not b.out.alm_high and b.out.state == OFF


def test_cannot_restart_while_alarm_active():
    b = running_boiler()
    b.estop_ok = False
    b.run(1)
    b.estop_ok = True
    b.press("start")
    assert b.out.state == FAULT                # needs an acknowledge first
    b.press("reset")
    b.press("start")
    b.run(3)
    assert b.out.state == RUN


def test_reset_is_refused_while_estop_still_pressed():
    b = running_boiler()
    b.estop_ok = False
    b.run(1)
    b.press("reset")
    assert b.out.alm_estop and b.out.state == FAULT
    b.estop_ok = True
    b.press("reset")
    assert not b.out.alm_estop and b.out.state == OFF
