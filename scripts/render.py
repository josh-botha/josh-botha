"""Renders the profile's animated SVGs from data/activity.json and data/asx200.json.

  assets/hero-{light,dark}.svg     the signal line from joshbotha.com: a
                                   heartbeat, the ASX 200, my commits as a
                                   running total, then the systems I've built
  assets/skyline-{light,dark}.svg  commits per day as an isometric city,
                                   shaded by Claude Code messages that day

GitHub shows READMEs through <img>, so there is no JavaScript and no font
loading: everything is CSS keyframes, and Geist is subset and embedded. Every
animation plays once and ends; nothing loops.

Run: python3 scripts/render.py   (needs fonttools and brotli)
"""

import base64
import io
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = Path.home() / "Developer/botha-site/node_modules/next/dist/next-devtools/server/font"
FONT_FILES = {"sans": FONT_DIR / "geist-latin.woff2", "mono": FONT_DIR / "geist-mono-latin.woff2"}

THEMES = {
    "light": {
        "ink": "#121419", "grey": "#6b707a", "dim": "#9a9ea7", "hair": "rgba(18,20,25,.14)",
        "grid": "rgba(18,20,25,.05)", "speck": (18, 20, 25), "grain": 0.07,
        "glowA": (60, 100, 230, 0.10), "glowB": (220, 130, 80, 0.10),
        # warm (human) to ink to blue (machine), as on the site
        "stops": [(0, (190, 98, 48)), (0.36, (32, 34, 40)), (0.62, (38, 52, 112)), (1, (38, 86, 236))],
        "ecg": "rgba(200,90,70,", "cell": "rgba(18,20,25,.07)",
        "ramp": ["#e8e9ed", "#d3dbf7", "#a6b7f1", "#6683e6", "#2547d8"],
        "shade": ("#1d2f86", 0.16, 0.34),
    },
    "dark": {
        "ink": "#eef1f6", "grey": "#9aa1ad", "dim": "#6b717c", "hair": "rgba(238,241,246,.16)",
        "grid": "rgba(238,241,246,.045)", "speck": (238, 241, 246), "grain": 0.06,
        "glowA": (80, 110, 255, 0.16), "glowB": (230, 140, 90, 0.10),
        "stops": [(0, (227, 139, 92)), (0.36, (214, 219, 228)), (0.62, (140, 160, 255)), (1, (109, 139, 255))],
        "ecg": "rgba(230,120,95,", "cell": "rgba(238,241,246,.07)",
        "ramp": ["#1c2029", "#1f2b55", "#2b4196", "#4565dc", "#7d98ff"],
        "shade": ("#070a16", 0.26, 0.46),
    },
}

EASE_IO = "cubic-bezier(.65,0,.35,1)"  # easeInOutCubic, matched by ease_io() below
EASE_OUT = "cubic-bezier(.2,.7,.2,1)"


# ── fonts ────────────────────────────────────────────────────────────────

class Face:
    """One static instance of a variable font: measures text and embeds a subset."""

    def __init__(self, kind: str, wght: int, family: str):
        self.path, self.wght, self.family = FONT_FILES[kind], wght, family
        self.font = self._instance()
        self.cmap = self.font.getBestCmap()
        self.hmtx = self.font["hmtx"]
        self.upm = self.font["head"].unitsPerEm
        self.used: set[str] = set()

    def _instance(self) -> TTFont:
        return instancer.instantiateVariableFont(TTFont(self.path), {"wght": self.wght})

    def width(self, text: str, size: float, track: float = 0) -> float:
        adv = sum(self.hmtx[self.cmap.get(ord(c), ".notdef")][0] for c in text)
        return adv / self.upm * size + track * size * len(text)

    def use(self, text: str) -> str:
        self.used.update(text)
        return text

    def face_css(self) -> str:
        if not self.used:
            return ""
        f = self._instance()
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga", "calt", "tnum"]
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(self.used)))
        sub.subset(f)
        buf = io.BytesIO()
        f.flavor = "woff2"
        f.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"@font-face{{font-family:{self.family};src:url(data:font/woff2;base64,{b64}) format('woff2')}}"


def faces():
    return {
        "s4": Face("sans", 400, "S4"), "s5": Face("sans", 500, "S5"), "s6": Face("sans", 600, "S6"),
        "m4": Face("mono", 400, "M4"), "m5": Face("mono", 500, "M5"),
    }


# ── helpers ──────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def n(v: float) -> str:
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def rgba(c, a=None) -> str:
    if a is None:
        return f"rgb({c[0]},{c[1]},{c[2]})"
    return f"rgba({c[0]},{c[1]},{c[2]},{a:g})"


def ease_io(t: float) -> float:
    t = min(1, max(0, t))
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def inv_ease_io(y: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ease_io(mid) < y else (lo, mid)
    return lo


def rdp(pts, eps):
    """Ramer-Douglas-Peucker, iterative, so long flat runs collapse to one segment."""
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x0, y0), (x1, y1) = pts[a], pts[b]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1e-9
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            d = abs(dy * pts[i][0] - dx * pts[i][1] + x1 * y0 - y1 * x0) / L
            if d > best:
                best, idx = d, i
        if best > eps:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def grain_defs(t) -> str:
    r, g, b = (v / 255 for v in t["speck"])
    return (
        '<filter id="grain" x="0" y="0" width="100%" height="100%">'
        '<feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" seed="11" stitchTiles="stitch"/>'
        f'<feColorMatrix values="0 0 0 0 {r:.3f} 0 0 0 0 {g:.3f} 0 0 0 0 {b:.3f} 3 0 0 0 -1.55"/>'
        "</filter>"
    )


def feather(id_, axis, edge):
    """A mask gradient that fades to nothing over `edge` (0..0.5) at both ends of an axis."""
    x2, y2 = ("1", "0") if axis == "x" else ("0", "1")
    return (
        f'<linearGradient id="{id_}" x1="0" y1="0" x2="{x2}" y2="{y2}">'
        f'<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="{edge}" stop-color="#fff"/>'
        f'<stop offset="{1 - edge}" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        "</linearGradient>"
    )


def svg_doc(W, H, title, css, body, fs) -> str:
    fonts = "".join(f.face_css() for f in fs.values())
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title><style>{fonts}{css}"
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>"
        f"{body}</svg>"
    )


BASE_CSS = (
    "@keyframes up{from{opacity:0;transform:translateY(14px)}}"
    "@keyframes in{from{opacity:0}}"
    "@keyframes draw{from{stroke-dashoffset:1}}"
    "@keyframes grow{from{transform:scaleY(0)}}"
    "@keyframes pop{from{opacity:0;transform:scale(.2)}}"
    "@keyframes rise{from{transform:translateY(105%)}}"
    f".up{{animation:up .9s {EASE_OUT} both}}"
    ".in{animation:in .5s ease-out both}"
)


# ── hero ─────────────────────────────────────────────────────────────────

SYSTEMS = [  # positions from the site's network field (src/lib/v9/content.ts), names left off
    (0.04, 0.58), (0.30, 0.30), (0.38, 0.74), (0.58, 0.12), (0.64, 0.50), (0.66, 0.92), (0.90, 0.30), (0.95, 0.72),
]
LINKS = [(0, 1), (0, 2), (1, 2), (1, 3), (1, 4), (3, 4), (2, 4), (2, 5), (4, 6), (4, 5), (5, 7), (6, 7), (3, 6)]


def weekly_commits(days: dict[str, int], weeks: int, today: date):
    monday = today - timedelta(days=today.weekday())
    out = []
    for i in range(weeks - 1, -1, -1):
        start = monday - timedelta(weeks=i)
        out.append(sum(days.get(str(start + timedelta(d)), 0) for d in range(7)))
    return out


def hero(theme: str, activity, asx, today: date) -> str:
    t = THEMES[theme]
    fs = faces()
    W, H = 1000, 610
    T0, SWEEP = 0.35, 2.9
    rnd = random.Random(20261010)

    seg = {"ecg": (30, 262), "market": (262, 500), "bars": (500, 712), "net": (728, 972)}
    base, amp = 470, 82
    band_top, band_bot = 352, 552

    # 1. heartbeat: the shape of an ECG, carrying no figure
    def ecg(u):
        return (0.08 * math.exp(-(((u - 0.2) / 0.035) ** 2)) - 0.11 * math.exp(-(((u - 0.38) / 0.011) ** 2))
                + 1.0 * math.exp(-(((u - 0.42) / 0.011) ** 2)) - 0.26 * math.exp(-(((u - 0.46) / 0.012) ** 2))
                + 0.17 * math.exp(-(((u - 0.68) / 0.05) ** 2)))

    e0, e1 = seg["ecg"]
    beat = (e1 - e0) / 2
    line = [(e0 + k * 0.25, base - amp * ecg(((k * 0.25) / beat) % 1)) for k in range(int((e1 - e0) / 0.25))]

    # 2. the ASX 200, two years of weekly closes, rebased so the first close sits on the baseline
    closes = [w["close"] for w in asx["weeks"]]
    m0, m1 = seg["market"]
    c0, cmax = closes[0], max(max(closes), closes[0] + 1)
    rise = 76
    market = [(m0 + (m1 - m0) * i / (len(closes) - 1), base - (c - c0) / (cmax - c0) * rise) for i, c in enumerate(closes)]
    for (ax, ay), (bx, by) in zip(market, market[1:]):
        steps = max(2, int((bx - ax) / 0.5))
        for k in range(steps):
            u = k / steps
            line.append((ax + (bx - ax) * u, ay + (by - ay) * u * u * (3 - 2 * u)))

    # 3. commits per week, as a running total that climbs into the network
    weeks = weekly_commits(activity["commits"]["days"], 26, today)
    b0, b1 = seg["bars"]
    slot = (b1 - b0) / len(weeks)
    bw = slot * 0.62
    bar_base = 540
    run, totals = 0, []
    for c in weeks:
        run += c
        totals.append(run)
    lo_c, hi_c = min(totals), max(totals)
    start_top = min(bar_base - 18, market[-1][1] + 6)
    end_top = 374
    bars = []
    for i, tot in enumerate(totals):
        f = 1 if hi_c == lo_c else (tot - lo_c) / (hi_c - lo_c)
        bars.append((b0 + i * slot + (slot - bw) / 2, start_top + (end_top - start_top) * f))
    px, py = market[-1]
    for bx, top in bars:
        line += [(px, py), (bx, top), (bx + bw, top)]
        px, py = bx + bw, top

    pts = rdp(line, 0.12)
    d_line = "M" + " L".join(f"{n(x)} {n(y)}" for x, y in pts)

    # head timing: the dash reveals arc length on an eased clock; invert it per x
    cum, acc = [0.0], 0.0
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        acc += math.hypot(bx - ax, by - ay)
        cum.append(acc)
    total_len = acc

    def t_at(x):
        for (px_, _), c in zip(pts, cum):
            if px_ >= x:
                return T0 + inv_ease_io(c / total_len) * SWEEP
        return T0 + SWEEP

    # particles along the line, grouped by when the head reaches them
    BUCK = 36
    groups: dict[tuple[int, int], list[str]] = {}
    alphas = [0.16, 0.32, 0.55]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        seglen = math.hypot(bx - ax, by - ay)
        for k in range(max(1, int(seglen / 1.1))):
            u = k / max(1, int(seglen / 1.1))
            x, y = ax + (bx - ax) * u, ay + (by - ay) * u
            for _ in range(2):
                wide = rnd.random() < 0.08
                sd = 6 if wide else 0.7 + rnd.random() * 1.6
                a = 0 if wide else rnd.choice((1, 1, 2))
                b = min(BUCK - 1, int((x - e0) / (seg["bars"][1] - e0) * BUCK))
                groups.setdefault((b, a), []).append(f"M{n(x + rnd.gauss(0, .5))} {n(y + rnd.gauss(0, sd))}h.01")
    # faint dust over the band
    for _ in range(420):
        x = rnd.uniform(20, W - 20)
        y = rnd.uniform(band_top + 10, band_bot - 6)
        b = min(BUCK - 1, max(0, int((min(x, seg["bars"][1]) - e0) / (seg["bars"][1] - e0) * BUCK)))
        groups.setdefault((b, 0), []).append(f"M{n(x)} {n(y)}h.01")

    # ── paper under each discipline: ECG grid, chart rules, spreadsheet cells, dot matrix
    ecg_c = t["ecg"]
    defs = [
        grain_defs(t),
        f'<linearGradient id="lg" gradientUnits="userSpaceOnUse" x1="{e0}" y1="0" x2="{seg["net"][1]}" y2="0">'
        + "".join(f'<stop offset="{o}" stop-color="{rgba(c)}"/>' for o, c in t["stops"]) + "</linearGradient>",
        f'<linearGradient id="bf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{rgba(t["stops"][3][1], .26)}"/>'
        f'<stop offset="1" stop-color="{rgba(t["stops"][3][1], .03)}"/></linearGradient>',
        f'<pattern id="pg" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" stroke="{t["grid"]}"/></pattern>',
        f'<pattern id="p-ecg" width="30" height="30" patternUnits="userSpaceOnUse" y="{band_top}">'
        f'<path d="M6 0V30M12 0V30M18 0V30M24 0V30M0 6H30M0 12H30M0 18H30M0 24H30" stroke="{ecg_c}.07)" stroke-width=".8"/>'
        f'<path d="M30 0H0V30" fill="none" stroke="{ecg_c}.16)" stroke-width=".8"/></pattern>',
        f'<pattern id="p-mkt" width="40" height="24" patternUnits="userSpaceOnUse" y="{band_top}"><path d="M0 24H40" stroke="{t["cell"]}"/></pattern>',
        f'<pattern id="p-xls" width="30" height="15" patternUnits="userSpaceOnUse" y="{band_top}"><path d="M30 0H0V15" fill="none" stroke="{t["cell"]}"/></pattern>',
        f'<pattern id="p-dot" width="11" height="11" patternUnits="userSpaceOnUse"><circle cx="5.5" cy="5.5" r=".9" fill="{t["cell"]}"/></pattern>',
        feather("fx", "x", 0.06), feather("fy", "y", 0.10), feather("sx", "x", 0.16), feather("sy", "y", 0.2),
        f'<mask id="mfx"><rect width="{W}" height="{H}" fill="url(#fx)"/></mask>',
        f'<mask id="mfy"><rect width="{W}" height="{H}" fill="url(#fy)"/></mask>',
        f'<radialGradient id="ga" cx=".82" cy=".78" r=".55"><stop offset="0" stop-color="{rgba(t["glowA"][:3], t["glowA"][3])}"/><stop offset="1" stop-color="{rgba(t["glowA"][:3], 0)}"/></radialGradient>',
        f'<radialGradient id="gb" cx=".06" cy=".84" r=".45"><stop offset="0" stop-color="{rgba(t["glowB"][:3], t["glowB"][3])}"/><stop offset="1" stop-color="{rgba(t["glowB"][:3], 0)}"/></radialGradient>',
    ]
    strips = []
    for k, (key, pat) in enumerate((("ecg", "p-ecg"), ("market", "p-mkt"), ("bars", "p-xls"), ("net", "p-dot"))):
        x0, x1 = seg[key]
        pad = 26
        defs.append(f'<mask id="ms{k}" maskUnits="userSpaceOnUse" x="{x0 - pad}" y="{band_top}" width="{x1 - x0 + 2 * pad}" height="{band_bot - band_top}">'
                    f'<rect x="{x0 - pad}" y="{band_top}" width="{x1 - x0 + 2 * pad}" height="{band_bot - band_top}" fill="url(#sx)"/></mask>'
                    f'<mask id="mt{k}"><rect x="0" y="{band_top}" width="{W}" height="{band_bot - band_top}" fill="url(#sy)"/></mask>')
        strips.append(f'<g mask="url(#mt{k})"><rect mask="url(#ms{k})" class="in" style="animation-delay:{t_at(x0) - .25:.2f}s;animation-duration:.8s" '
                      f'x="{x0 - pad}" y="{band_top}" width="{x1 - x0 + 2 * pad}" height="{band_bot - band_top}" fill="url(#{pat})"/></g>')

    # ── copy
    s4, s5, s6, m4, m5 = fs["s4"], fs["s5"], fs["s6"], fs["m4"], fs["m5"]
    css = BASE_CSS + (
        f".k{{font-family:M4,ui-monospace,Menlo,monospace;font-size:13px;letter-spacing:.14em;fill:{t['grey']}}}"
        f".nm{{font-family:S6,'Helvetica Neue',Arial,sans-serif;font-size:118px;letter-spacing:-.058em;fill:{t['ink']}}}"
        f".cl{{font-family:S5,'Helvetica Neue',Arial,sans-serif;font-size:28px;letter-spacing:-.03em;fill:{t['grey']}}}"
        f".cl .i{{fill:{t['ink']}}}"
        f".nw{{font-family:S4,'Helvetica Neue',Arial,sans-serif;font-size:16.5px;fill:{t['grey']}}}.nw .b{{font-family:S5,'Helvetica Neue',Arial,sans-serif;fill:{t['ink']}}}"
        f".sl{{font-family:M5,ui-monospace,Menlo,monospace;font-size:11.5px;letter-spacing:.14em;fill:{t['grey']}}}"
        f".ss{{font-family:M4,ui-monospace,Menlo,monospace;font-size:11.5px;fill:{t['dim']}}}"
        f".ln{{fill:none;stroke:url(#lg);stroke-width:1.7;stroke-linejoin:round;stroke-dasharray:1 1;animation:draw {SWEEP}s {EASE_IO} {T0}s both}}"
        ".pt{fill:none;stroke:url(#lg);stroke-linecap:round}"
        ".bar{transform-box:fill-box;transform-origin:50% 100%;animation:grow .45s cubic-bezier(.2,.8,.2,1) both}"
        ".ed{fill:none;stroke:url(#lg);stroke-width:1;stroke-dasharray:1 1;animation:draw .5s ease-out both}"
        ".nd{transform-box:fill-box;transform-origin:50% 50%;animation:pop .6s cubic-bezier(.2,.9,.25,1.2) both}"
    )

    out = []
    # atmosphere: grid, two glows and grain, feathered so there is no box edge on GitHub
    out.append(f'<g mask="url(#mfy)"><g mask="url(#mfx)">'
               f'<rect width="{W}" height="{H}" fill="url(#pg)"/>'
               f'<rect width="{W}" height="{H}" fill="url(#ga)"/><rect width="{W}" height="{H}" fill="url(#gb)"/>'
               f'<rect width="{W}" height="{H}" filter="url(#grain)" opacity="{t["grain"]}"/></g></g>')
    out += strips

    out.append(f'<text class="k up" x="40" y="66" style="animation-delay:.05s">{m4.use("CONNECTING HUMANS AND AI")}</text>')
    out.append(f'<text class="nm up" x="33" y="172" style="animation-delay:.12s">{s6.use("Josh Botha")}</text>')
    out.append(f'<text class="cl up" x="40" y="226" style="animation-delay:.28s">{s5.use("Medical science, finance and business intelligence,")}</text>')
    out.append(f'<text class="cl up" x="40" y="262" style="animation-delay:.36s"><tspan class="i">{s5.use("with AI as the future.")}</tspan></text>')
    out.append(f'<text class="nw up" x="40" y="306" style="animation-delay:.5s">{s4.use("Currently at ")}<tspan class="b">{fs["s5"].use("Project2100")}</tspan>'
               f'{s4.use(" · systems consulting and full-stack development")}</text>')

    # bars under the staircase grow from the floor after the head passes
    bar_rects = []
    for bx, top in bars:
        h = bar_base - top
        bar_rects.append(f'<rect class="bar" style="animation-delay:{t_at(bx) + .04:.2f}s" x="{n(bx)}" y="{n(top)}" width="{n(bw)}" height="{n(h)}" fill="url(#bf)"/>')
    out.append("<g>" + "".join(bar_rects) + "</g>")

    # particles, then the crisp line on top
    pg = []
    for (b, a), ds in sorted(groups.items()):
        bx = e0 + (b + 0.5) / BUCK * (seg["bars"][1] - e0)
        sw = 1.25 if a else 1.0
        pg.append(f'<path class="pt in" style="animation-delay:{t_at(bx):.2f}s;stroke-width:{sw}" stroke-opacity="{alphas[a]}" d="{"".join(ds)}"/>')
    out.append("<g>" + "".join(pg) + "</g>")
    out.append(f'<path class="ln" pathLength="1" d="{d_line}"/>')

    # 4. the network: systems I've built, linked where they share work or technology
    n0, n1 = seg["net"]
    ny0, ny1 = 378, 528
    nodes = [(n0 + x * (n1 - n0), ny0 + y * (ny1 - ny0)) for x, y in SYSTEMS]
    net_t0 = T0 + SWEEP - 0.05
    entry = (bars[-1][0] + bw, bars[-1][1])
    edges = [(entry, nodes[0])] + [(nodes[a], nodes[b]) for a, b in LINKS]
    ed = []
    for k, (A, B) in enumerate(edges):
        ed.append(f'<path class="ed" pathLength="1" style="animation-delay:{net_t0 + k / len(edges) * .75:.2f}s" d="M{n(A[0])} {n(A[1])}L{n(B[0])} {n(B[1])}"/>')
    out.append(f'<g stroke-opacity=".55">{"".join(ed)}</g>')
    nd = []
    for k, (x, y) in enumerate(nodes):
        r = 3.6 + rnd.random() * 2.6
        dots = "".join(f"M{n(x + rnd.gauss(0, r))} {n(y + rnd.gauss(0, r))}h.01" for _ in range(70))
        nd.append(f'<g class="nd" style="animation-delay:{net_t0 + (k + 1) / len(nodes) * .9:.2f}s">'
                  f'<path class="pt" stroke-width="1.3" stroke-opacity=".5" d="{dots}"/>'
                  f'<circle cx="{n(x)}" cy="{n(y)}" r="2.6" fill="url(#lg)"/></g>')
    out.append("<g>" + "".join(nd) + "</g>")

    # labels under each discipline, as the head reaches them
    labels = [
        ("ecg", "MEDICAL SCIENCE", "a heartbeat"),
        ("market", "FINANCE", "the ASX 200, two years"),
        ("bars", "BUSINESS INTELLIGENCE", "my commits, a running total"),
        ("net", "AI SYSTEMS DESIGN", "the systems I've built"),
    ]
    for key, big, small in labels:
        x0, x1 = seg[key]
        cx = (x0 + x1) / 2
        d = t_at(cx) if key != "net" else net_t0 + .35
        out.append(f'<g class="up" style="animation-delay:{d:.2f}s"><text class="sl" x="{n(cx)}" y="576" text-anchor="middle">{m5.use(big)}</text>'
                   f'<text class="ss" x="{n(cx)}" y="594" text-anchor="middle">{m4.use(small)}</text></g>')

    title = "Josh Botha. Medical science, finance and business intelligence, with AI as the future."
    return svg_doc(W, H, title, css, "<defs>" + "".join(defs) + "</defs>" + "".join(out), fs)


# ── skyline ──────────────────────────────────────────────────────────────

def skyline(theme: str, activity, today: date, start: date) -> str:
    t = THEMES[theme]
    fs = faces()
    s4, s5, m4, m5 = fs["s4"], fs["s5"], fs["m4"], fs["m5"]
    W, H = 1000, 600
    commits = activity["commits"]["days"]
    msgs = activity["claude"]["days"]
    starts = activity["claude"]["starts"]

    weeks = (today - start).days // 7 + 1
    ux, uy, vx, vy = 56, 15, -28, 14
    ox, oy = 342, 292
    peak = max(commits.get(str(start + timedelta(d)), 0) for d in range((today - start).days + 1))

    def P(i, j, z=0.0):
        return (ox + i * ux + j * vx, oy + i * uy + j * vy - z)

    def poly(ps, fill, extra=""):
        return f'<polygon points="{" ".join(f"{n(x)},{n(y)}" for x, y in ps)}" fill="{fill}"{extra}/>'

    def level(m):
        return 0 if m == 0 else 1 if m <= 100 else 2 if m <= 500 else 3 if m <= 2000 else 4

    def shade(hex_, f):
        """Mix toward a deep blue rather than black, so low shades stay blue instead of going grey."""
        to = t["shade"][0]
        a = [int(hex_[k:k + 2], 16) for k in (1, 3, 5)]
        b = [int(to[k:k + 2], 16) for k in (1, 3, 5)]
        return "#" + "".join(f"{round(x + (y - x) * f):02x}" for x, y in zip(a, b))

    cells = []
    for i in range(weeks):
        for j in range(7):
            d = start + timedelta(weeks=i, days=j)
            if d > today:
                continue
            cells.append((i, j, d, commits.get(str(d), 0), msgs.get(str(d), 0)))

    g = 0.12
    tiles, towers, clips = [], [], []
    for i, j, d, c, m in cells:
        top = t["ramp"][level(m)]
        fr, rt = shade(top, t["shade"][1]), shade(top, t["shade"][2])
        A, B, C, D = (i + g, j + g), (i + 1 - g, j + g), (i + 1 - g, j + 1 - g), (i + g, j + 1 - g)
        slab = 3
        tiles.append((i, f'<g class="in" style="animation-delay:{.15 + i * .05:.2f}s">'
                      + poly([P(*A, slab), P(*B, slab), P(*C, slab), P(*D, slab)], top)
                      + poly([P(*D), P(*C), P(*C, slab), P(*D, slab)], fr)
                      + poly([P(*B), P(*C), P(*C, slab), P(*B, slab)], rt) + "</g>"))
        if c == 0:
            continue
        h = 10 + 196 * math.sqrt(c / peak)
        D0, C0, B0 = P(*D), P(*C), P(*B)
        cid = f"c{i}_{j}"
        clips.append(f'<clipPath id="{cid}"><polygon points="{n(D0[0])},0 {n(D0[0])},{n(D0[1])} {n(C0[0])},{n(C0[1])} {n(B0[0])},{n(B0[1])} {n(B0[0])},0"/></clipPath>')
        delay = 0.85 + i * 0.12 + j * 0.025
        towers.append((i + j, i, j, d, c, m, h,
                       f'<g clip-path="url(#{cid})"><g class="tw" style="animation-delay:{delay:.2f}s">'
                       + poly([P(*D), P(*C), P(*C, h), P(*D, h)], fr)
                       + poly([P(*B), P(*C), P(*C, h), P(*B, h)], rt)
                       + poly([P(*A, h), P(*B, h), P(*C, h), P(*D, h)], top) + "</g></g>"))
    towers.sort(key=lambda r: (r[0], r[1]))
    last_rise = max(0.85 + r[1] * 0.12 + r[2] * 0.025 for r in towers) + 0.9

    css = BASE_CSS + (
        f".k{{font-family:M4,ui-monospace,Menlo,monospace;font-size:13px;letter-spacing:.14em;fill:{t['grey']}}}"
        f".h1{{font-family:S5,'Helvetica Neue',Arial,sans-serif;font-size:31px;letter-spacing:-.03em;fill:{t['ink']}}}"
        f".h2{{font-family:S5,'Helvetica Neue',Arial,sans-serif;font-size:31px;letter-spacing:-.03em;fill:{t['grey']}}}"
        f".lb{{font-family:M5,ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.14em;fill:{t['dim']}}}"
        f".lt{{font-family:S4,'Helvetica Neue',Arial,sans-serif;font-size:14px;fill:{t['grey']}}}"
        f".ro{{font-family:S5,'Helvetica Neue',Arial,sans-serif;font-size:15px;fill:{t['ink']}}}"
        f".rs{{font-family:M4,ui-monospace,Menlo,monospace;font-size:12px;fill:{t['grey']}}}"
        f".mo{{font-family:M4,ui-monospace,Menlo,monospace;font-size:11.5px;letter-spacing:.12em;fill:{t['dim']}}}"
        f".tw{{transform-box:fill-box;animation:rise .85s {EASE_OUT} both}}"
    )

    win_commits = sum(c for *_, c, _m in cells)
    win_sessions = sum(v for k, v in starts.items() if str(start) <= k <= str(today))
    first, last = start.strftime("%-d %B").upper(), today.strftime("%-d %B %Y").upper()

    out = [
        '<defs>', grain_defs(t), "".join(clips),
        f'<radialGradient id="ga" cx=".66" cy=".62" r=".5"><stop offset="0" stop-color="{rgba(t["glowA"][:3], t["glowA"][3] * .8)}"/><stop offset="1" stop-color="{rgba(t["glowA"][:3], 0)}"/></radialGradient>',
        feather("fx", "x", .08), feather("fy", "y", .1),
        f'<mask id="mfx"><rect width="{W}" height="{H}" fill="url(#fx)"/></mask><mask id="mfy"><rect width="{W}" height="{H}" fill="url(#fy)"/></mask>',
        "</defs>",
        f'<g mask="url(#mfy)"><g mask="url(#mfx)"><rect width="{W}" height="{H}" fill="url(#ga)"/>'
        f'<rect width="{W}" height="{H}" filter="url(#grain)" opacity="{t["grain"]}"/></g></g>',
        f'<text class="k up" x="40" y="62">{m4.use(f"{first} TO {last}")}</text>',
        f'<text class="h1 up" x="40" y="108" style="animation-delay:.1s">{s5.use(f"{win_commits:,} commits and {win_sessions:,} Claude Code sessions")}</text>',
        f'<text class="h2 up" x="40" y="146" style="animation-delay:.2s">{s5.use(f"in {weeks - 1} weeks, all in private repos.")}</text>',
    ]
    # ground plate
    out += [s for _, s in sorted(tiles, key=lambda r: r[0])]
    out += [r[7] for r in towers]

    # month marks along the front edge
    seen = set()
    for i in range(weeks):
        for dd in range(7):
            d = start + timedelta(weeks=i, days=dd)
            if d.day == 1 or (i == 0 and dd == 0):
                if d.month in seen or d > today:
                    continue
                seen.add(d.month)
                x, y = P(i + 0.5, 7.55)
                out.append(f'<text class="mo in" style="animation-delay:{.3 + i * .05:.2f}s" x="{n(x)}" y="{n(y + 12)}" text-anchor="middle">{m4.use(d.strftime("%b").upper())}</text>')

    # the busiest day, read out once everything has risen
    bi, bj, bd, bc, bm, bh = max(((r[1], r[2], r[3], r[4], r[5], r[6]) for r in towers), key=lambda r: r[3])
    tx, ty = P(bi + 0.5, bj + 0.5, bh)
    ly = ty - 46
    out.append(f'<g class="up" style="animation-delay:{last_rise:.2f}s">'
               f'<path d="M{n(tx)} {n(ty - 4)}V{n(ly)}" stroke="{t["ink"]}" stroke-width="1"/>'
               f'<circle cx="{n(tx)}" cy="{n(ty - 4)}" r="2.5" fill="{t["ink"]}"/>'
               f'<text class="ro" x="{n(tx - 10)}" y="{n(ly + 4)}" text-anchor="end">{s5.use(bd.strftime("%a %-d %b"))}</text>'
               f'<text class="rs" x="{n(tx - 10)}" y="{n(ly + 23)}" text-anchor="end">{m4.use(f"{bc} commits · {bm:,} messages")}</text></g>')

    # legend
    lx, ly0 = 40, 520
    sw = "".join(f'<rect x="{lx + 64 + k * 15}" y="{ly0 + 26}" width="11" height="11" fill="{t["ramp"][k]}"/>' for k in range(5))
    out.append(f'<g class="in" style="animation-delay:{last_rise + .2:.2f}s">'
               f'<text class="lb" x="{lx}" y="{ly0 + 10}">{m5.use("HEIGHT")}</text><text class="lt" x="{lx + 64}" y="{ly0 + 11}">{s4.use("commits that day")}</text>'
               f'<text class="lb" x="{lx}" y="{ly0 + 36}">{m5.use("SHADE")}</text>{sw}'
               f'<text class="lt" x="{lx + 64 + 5 * 15 + 6}" y="{ly0 + 37}">{s4.use("Claude Code messages that day")}</text></g>')

    title = f"{win_commits} commits and {win_sessions} Claude Code sessions in {weeks - 1} weeks, drawn as a city of daily commits."
    return svg_doc(W, H, title, css, "".join(out), fs)


if __name__ == "__main__":
    activity = json.loads((ROOT / "data/activity.json").read_text())
    asx = json.loads((ROOT / "data/asx200.json").read_text())
    today = date.fromisoformat(activity["generated"])
    start = date(2026, 8, 3)
    (ROOT / "assets").mkdir(exist_ok=True)
    for theme in THEMES:
        for name, svg in (("hero", hero(theme, activity, asx, today)), ("skyline", skyline(theme, activity, today, start))):
            p = ROOT / f"assets/{name}-{theme}.svg"
            p.write_text(svg)
            print(f"{p.relative_to(ROOT)}  {len(svg) / 1024:.0f} KB")
    # keep the README's alt text in step with the numbers just drawn
    import re
    readme = ROOT / "README.md"
    c = sum(v for k, v in activity["commits"]["days"].items() if str(start) <= k <= str(today))
    s = sum(v for k, v in activity["claude"]["starts"].items() if str(start) <= k <= str(today))
    days = {k: v for k, v in activity["commits"]["days"].items() if str(start) <= k <= str(today)}
    busy = max(days, key=days.get)
    bd = date.fromisoformat(busy)
    alt = (f"{c} commits and {s} Claude Code sessions between {start.strftime('%-d %B')} and {today.strftime('%-d %B %Y')}, "
           f"drawn as a city with one tower per day. Height is commits, shade is Claude Code messages. "
           f"The busiest day was {bd.strftime('%A %-d %B')}: {days[busy]} commits and {activity['claude']['days'].get(busy, 0):,} messages.")
    text = readme.read_text()
    readme.write_text(re.sub(r'(<img alt=")[^"]*(" src="assets/skyline-light\.svg")', lambda m: m[1] + alt + m[2], text))
