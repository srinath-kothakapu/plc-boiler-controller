"""Generate the figures used in the README (docs/*.svg)."""
import os, sys
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.fonttype"] = "none"
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(__file__))
from plant import Boiler

DOCS = os.path.join(os.path.dirname(__file__), "..", "docs")


def plot(b, title, fname, extra_lines=()):
    log = b.log[::20]   # one point per 2 s keeps the SVG small
    t = [r[0] for r in log]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 5.2), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1.5]})
    a1.plot(t, [r[1] for r in log], label="water temperature")
    a1.plot(t, [r[10] for r in log], "--", label="setpoint")
    for y, lab in extra_lines:
        a1.axhline(y, color="r", ls=":", label=lab)
    a1.set_ylabel("degC"); a1.set_title(title); a1.legend(loc="lower right"); a1.grid(alpha=.3)
    a2.plot(t, [r[2] if r[3] else 0 for r in log], label="PLC power command %")
    a2.plot(t, [10 * r[5] for r in log], label="state x10 (3 = FAULT)")
    a2.set_xlabel("time [s]"); a2.legend(loc="upper right"); a2.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(DOCS, fname)); plt.close(fig)


b = Boiler(setpoint=80.0); b.press("start"); b.run(1800)
plot(b, "Start-up and setpoint control (80 degC)", "startup.svg")


b = Boiler(setpoint=80.0); b.press("start"); b.run(120); b.contactor_welded = True
b.run(3000, until=lambda s: s.out.alm_high); b.run(300)
plot(b, "Welded heater contactor: software high limit trips at 95 degC", "high_limit.svg",
     extra_lines=[(95, "high limit 95 degC")])
print("plots written")
