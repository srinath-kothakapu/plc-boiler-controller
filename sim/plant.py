"""Simulation harness: the MATIEC-compiled PLC program (libplc.so) is stepped
one scan at a time against a simple first-order boiler model.

Plant model (lumped water mass):
    C * dT/dt = P_max * power/100 - k_loss * (T - T_amb) - P_load
"""
import ctypes, os
from dataclasses import dataclass, field

LIB = os.path.join(os.path.dirname(__file__), "..", "build", "libplc.so")
DT = 0.1  # s, must equal CycleS in boiler_ctrl.st


class In(ctypes.Structure):
    _fields_ = [("temp_c", ctypes.c_float), ("pump_running", ctypes.c_int),
                ("estop_ok", ctypes.c_int), ("start", ctypes.c_int),
                ("stop", ctypes.c_int), ("reset", ctypes.c_int),
                ("setpoint_c", ctypes.c_float)]


class Out(ctypes.Structure):
    _fields_ = [("pump_cmd", ctypes.c_int), ("burner_enable", ctypes.c_int),
                ("power_pct", ctypes.c_float), ("state", ctypes.c_int),
                ("alm_high", ctypes.c_int), ("alm_sensor", ctypes.c_int),
                ("alm_noflow", ctypes.c_int), ("alm_estop", ctypes.c_int)]


STATES = {0: "OFF", 1: "PUMP_START", 2: "RUN", 3: "FAULT"}


@dataclass
class Boiler:
    """Plant + PLC in one object. Inputs are plain attributes you can change
    between steps; fault injection flags simulate real-world failures."""
    setpoint: float = 80.0
    t_amb: float = 20.0
    temp: float = 20.0
    c_water: float = 2.0e5      # J/K
    p_max: float = 20e3         # W
    k_loss: float = 40.0        # W/K
    p_load: float = 0.0         # W, heat drawn by the process
    pump_delay: float = 1.0     # s until pump feedback follows the command
    # operator inputs
    start: bool = False
    stop: bool = False
    reset: bool = False
    estop_ok: bool = True
    # fault injection
    pump_broken: bool = False       # pump never runs / stops running
    contactor_welded: bool = False  # heater stays at 100 % regardless of PLC
    sensor_override: float = None   # value the PLC sees instead of the real temp
    # bookkeeping
    t: float = 0.0
    _pump_timer: float = 0.0
    pump_fb: bool = False
    out: Out = field(default_factory=Out)
    log: list = field(default_factory=list)

    def __post_init__(self):
        self.lib = ctypes.CDLL(os.path.abspath(LIB))
        self.lib.plc_init()
        self.temp = self.t_amb
        self.step()  # first scan with everything idle

    def step(self):
        seen = self.temp if self.sensor_override is None else self.sensor_override
        inp = In(seen, int(self.pump_fb), int(self.estop_ok), int(self.start),
                 int(self.stop), int(self.reset), self.setpoint)
        self.lib.plc_scan(ctypes.byref(inp), ctypes.byref(self.out))
        o = self.out
        # --- plant ---
        power = 100.0 if self.contactor_welded else (o.power_pct if o.burner_enable else 0.0)
        dT = (self.p_max * power / 100.0 - self.k_loss * (self.temp - self.t_amb)
              - self.p_load) / self.c_water
        self.temp += dT * DT
        # pump feedback follows command after a delay unless broken
        if o.pump_cmd and not self.pump_broken:
            self._pump_timer += DT
            self.pump_fb = self._pump_timer >= self.pump_delay
        else:
            self._pump_timer = 0.0
            self.pump_fb = False
        self.t += DT
        self.log.append((self.t, self.temp, o.power_pct, o.burner_enable,
                         o.pump_cmd, o.state, o.alm_high, o.alm_sensor,
                         o.alm_noflow, o.alm_estop, self.setpoint))

    def run(self, seconds, until=None):
        for _ in range(int(round(seconds / DT))):
            self.step()
            if until and until(self):
                return True
        return until is None

    def press(self, name, seconds=0.5):
        setattr(self, name, True); self.run(seconds); setattr(self, name, False); self.step()  # one scan with the button released
