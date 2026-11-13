"""Generate the figures used in the README (docs/*.svg).
Writes small, dependency-free SVG files (no matplotlib needed)."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from plant import Boiler

DOCS = os.path.join(os.path.dirname(__file__), "..", "docs")
W, H = 640, 400
X0, X1 = 60, 620            # plot area, x
TOP = (40, 230)             # temperature panel, y
BOT = (270, 360)            # power panel, y


def poly(xs, ys, x_to_px, y_to_px, color, dash=""):
    p = [(round(x_to_px(x)), round(y_to_px(y))) for x, y in zip(xs, ys)]
    p = [q for i, q in enumerate(p)                      # drop points on flat runs
         if 0 < i < len(p) - 1 and not (p[i-1][1] == q[1] == p[i+1][1]) or i in (0, len(p) - 1)]
    pts = " ".join(f"{x},{y}" for x, y in p)
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6"{d}/>'


def panel(y0, y1, lo, hi, ticks, unit):
    s = f'<rect x="{X0}" y="{y0}" width="{X1-X0}" height="{y1-y0}" fill="#fff" stroke="#999"/>'
    for t in ticks:
        y = y1 - (t - lo) / (hi - lo) * (y1 - y0)
        s += f'<line x1="{X0}" x2="{X1}" y1="{y:.1f}" y2="{y:.1f}" stroke="#ddd"/>'
        s += f'<text x="{X0-6}" y="{y+4:.1f}" text-anchor="end" font-size="11">{t}</text>'
    s += f'<text x="14" y="{(y0+y1)/2:.0f}" font-size="11" transform="rotate(-90 14 {(y0+y1)/2:.0f})" text-anchor="middle">{unit}</text>'
    return s


def plot(b, title, fname, limit=None, tmax=None):
    log = b.log[::200]                                  # one point per 20 s
    t = [r[0] for r in log]
    tmax = tmax or t[-1]
    xp = lambda v: X0 + v / tmax * (X1 - X0)
    lo, hi = 0, max(120, max(r[1] for r in log) + 5)
    yt = lambda v: TOP[1] - (v - lo) / (hi - lo) * (TOP[1] - TOP[0])
    yb = lambda v: BOT[1] - v / 100 * (BOT[1] - BOT[0])
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#fff"/>',
         f'<text x="{W/2}" y="22" text-anchor="middle" font-size="14" font-weight="bold">{title}</text>',
         panel(TOP[0], TOP[1], lo, hi, [t for t in range(0, int(hi) + 1, 20)], "degC"),
         poly(t, [r[1] for r in log], xp, yt, "#1f77b4"),
         poly(t, [r[10] for r in log], xp, yt, "#ff7f0e", "6,3")]
    if limit:
        s.append(poly([0, tmax], [limit, limit], xp, yt, "#d00", "2,3"))
    s.append(panel(BOT[0], BOT[1], 0, 100, [0, 50, 100], "power %"))
    s.append(poly(t, [r[2] if r[3] else 0 for r in log], xp, yb, "#1f77b4"))
    s.append(poly(t, [33 * r[5] for r in log], xp, yb, "#2a9d4a"))
    for v in range(0, int(tmax) + 1, 200 if tmax <= 1200 else 500):
        s.append(f'<text x="{xp(v):.0f}" y="378" text-anchor="middle" font-size="11">{v}</text>')
    s.append(f'<text x="{(X0+X1)/2}" y="396" text-anchor="middle" font-size="11">time [s]</text>')
    lg = [("#1f77b4", "water temperature / PLC power command"), ("#ff7f0e", "setpoint"),
          ("#2a9d4a", "state (33 = RUN, 100 = FAULT)")]
    if limit: lg.append(("#d00", f"high limit {limit} degC"))
    for i, (c, txt) in enumerate(lg):
        s.append(f'<line x1="{X0+8}" x2="{X0+30}" y1="{TOP[0]+12+i*14}" y2="{TOP[0]+12+i*14}" stroke="{c}" stroke-width="2"/>'
                 f'<text x="{X0+36}" y="{TOP[0]+16+i*14}" font-size="11">{txt}</text>')
    s.append("</svg>")
    with open(os.path.join(DOCS, fname), "w") as f:
        f.write("\n".join(s))


b = Boiler(setpoint=80.0); b.press("start"); b.run(1800)
plot(b, "Start-up and setpoint control (80 degC)", "startup.svg")

b = Boiler(setpoint=80.0); b.press("start"); b.run(120); b.contactor_welded = True
b.run(3000, until=lambda s: s.out.alm_high); b.run(300)
plot(b, "Welded heater contactor: software high limit trips at 95 degC", "high_limit.svg", limit=95)
print("plots written")
