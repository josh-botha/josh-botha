"""The README hero: the orb from the "Ask me about my work" band on joshbotha.com, drawn as a looping SVG.

One cloud of dots flies through twelve shapes, two per topic, then the topic's overview fades in.
Shape positions are the site's own (src/components/v9/home/morph.ts, settled, projected, saved in
data/work-shapes.json). Pure SVG/SMIL: no script, nothing leaves GitHub's image proxy.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import ROOT, THEMES, esc, faces, svg_doc, n  # noqa: E402

SHAPES = json.loads((ROOT / "data/work-shapes.json").read_text())
STRIDE = 2  # 486 dots -> 243
SCENE, MORPH = 3.4, 0.9  # seconds per topic, seconds a morph takes
EASE = "0.65 0 0.35 1"
TOPICS = [
    ("Web and app", "design", "#ff4fd8", ("browser", "phone"), ("Laying out the page", "Fitting it to a phone"),
     "Websites and app interfaces for the web, desktop and phones, from the first layout to the motion."),
    ("Systems", "design", "#33d69f", ("graph", "cube"), ("Mapping the systems", "Solving the puzzle"),
     "I map every system and manual step, then design and build the one system that connects them."),
    ("Data", "design", "#3d9bff", ("discs", "schema"), ("Reading the databases", "Modelling the data"),
     "Data modelled so every number has an owner, a source and a period, for reports, apps and AI."),
    ("AI", "implementation", "#8b5cff", ("neural", "agents"), ("Wiring the model", "Briefing the agents"),
     "Assistants and agents on a team's own data. Agents draft, and a person approves anything that leaves."),
    ("Finance", "and BI", "#ffad33", ("bars", "donut"), ("Building the P&L", "Reconciling to the cent"),
     "Weekly P&Ls that build themselves, board packs, and the systems behind them, reconciled to the cent."),
    ("Medical", "science", "#ff5a3c", ("helix", "ecg"), ("Reading the science", "Checking the pulse"),
     "Medical science and finance at the University of Sydney, and a published paper on 4-iodopyrimidine."),
]
LAYOUTS = {
    "wide": dict(W=1000, H=560, cx=738, cy=288, R=232, x=64, kick=64, prompt=156, t1=236, t2=300, tsz=56, label=356,
                 ov=392, ovsz=15.5, ovw=420, lead=25, ticks=506, tickw=58, url_x=936),
    "tall": dict(W=480, H=730, cx=240, cy=228, R=156, x=36, kick=46, prompt=432, t1=484, t2=524, tsz=36, label=566,
                 ov=596, ovsz=14, ovw=408, lead=21, ticks=696, tickw=54, url_x=444),
}


def mix(hex_, to, f):
    h = int(hex_[1:], 16)
    c = [(h >> 16) & 255, (h >> 8) & 255, h & 255]
    return "#" + "".join(f"{round(a + (b - a) * f):02x}" for a, b in zip(c, to))


def wrap(face, text, size, width):
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if face.width(t, size) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + [cur]


def kt(v):
    return f"{min(1, max(0, v)):.3f}".rstrip("0").rstrip(".") or "0"


def build(theme, layout, animated=True):
    T, L = THEMES[theme], LAYOUTS[layout]
    W, H = L["W"], L["H"]
    fs = faces()
    s4, s5, s6, m4 = fs["s4"], fs["s5"], fs["s6"], fs["m4"]
    dark = theme == "dark"
    total = SCENE * len(TOPICS)
    hue = [mix(t[2], (18, 20, 25), 0.0 if dark else 0.28) for t in TOPICS]
    order = [sid for t in TOPICS for sid in t[3]]
    unit = L["R"] / 116 * 1.12 * 0.9
    out = []
    css = (f".t{{font-family:S6;fill:{T['ink']};letter-spacing:-.03em}}.p{{font-family:S4;fill:{T['grey']}}}"
           f".k{{font-family:M4;fill:{T['dim']};letter-spacing:.08em}}.l{{font-family:M4;letter-spacing:.04em}}")
    out.append(f'<rect width="{W}" height="{H}" fill="{"#0b0d12" if dark else "#fbfbfd"}"/>')

    # constant chrome
    k = "JOSH BOTHA / DEVELOPER, SYDNEY"
    out.append(f'<text class="k" x="{L["x"]}" y="{L["kick"]}" font-size="12">{m4.use(k)}</text>')
    out.append(f'<text class="k" x="{L["url_x"]}" y="{L["kick"]}" font-size="12" text-anchor="end">{m4.use("JOSHBOTHA.COM")}</text>')
    out.append(f'<text class="p" x="{L["x"]}" y="{L["prompt"]}" font-size="{20 if layout == "wide" else 16}">{s4.use("Ask me about my work.")}</text>')

    # the dots
    idx = list(range(0, 486, STRIDE))
    dots = []
    for i in idx:
        base = SHAPES[order[-1]][i]
        x0, y0, r0 = base[0], base[1], base[2]
        if not animated:
            sid = order[1]
            p = SHAPES[sid][i]
            dots.append(f'<circle cx="{n(L["cx"] + p[0] * L["R"])}" cy="{n(L["cy"] + p[1] * L["R"])}" r="{p[2] * unit:.1f}"/>')
            continue
        times, cxs, cys, rs = [0.0], [], [], []
        cx = lambda p: str(round(L["cx"] + p[0] * L["R"]))
        cy = lambda p: str(round(L["cy"] + p[1] * L["R"]))
        rr = lambda p: f"{p[2] * unit:.1f}".rstrip("0").rstrip(".")
        cxs, cys, rs = [cx(base)], [cy(base)], [rr(base)]
        prev, last_t = base, 0.0
        for e, sid in enumerate(order):
            p = SHAPES[sid][i]
            t0 = (e // 2) * SCENE + (e % 2) * (SCENE * 0.5)
            start = t0 + p[5] * 0.45 * MORPH
            end = start + 0.55 * MORPH
            if start > last_t + 1e-3:
                times.append(start / total); cxs.append(cx(prev)); cys.append(cy(prev)); rs.append(rr(prev))
            times.append(end / total); cxs.append(cx(p)); cys.append(cy(p)); rs.append(rr(p))
            prev, last_t = p, end
        if last_t < total - 1e-3:
            times.append(1.0); cxs.append(cx(prev)); cys.append(cy(prev)); rs.append(rr(prev))
        else:
            times[-1] = 1.0
        ks = ";".join(kt(v) for v in times)
        a = lambda attr, vals: f'<animate attributeName="{attr}" values="{";".join(vals)}" keyTimes="{ks}" dur="{total:g}s" repeatCount="indefinite"/>'
        sp = f'calcMode="spline" keySplines="{";".join([EASE] * (len(times) - 1))}" '
        ae = lambda attr, vals: f'<animate attributeName="{attr}" {sp}values="{";".join(vals)}" keyTimes="{ks}" dur="{total:g}s" repeatCount="indefinite"/>'
        dots.append(f'<circle cx="{cxs[0]}" cy="{cys[0]}" r="{rs[0]}">{ae("cx", cxs)}{ae("cy", cys)}{a("r", rs)}</circle>')
    if animated:
        # the hue changes as each scene's first shape arrives
        hk = "0;" + ";".join(kt((j * SCENE + 0.55) / total) for j in range(1, len(hue))) + ";1"
        vals = ";".join(hue) + ";" + hue[-1]
        fillanim = f'<animate attributeName="fill" calcMode="discrete" values="{vals}" keyTimes="{hk}" dur="{total:g}s" repeatCount="indefinite"/>'
        out.append(f'<defs><filter id="g" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="{L["R"] / 30:.1f}"/></filter><filter id="b" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="{L["R"] / 3.2:.0f}"/></filter></defs>')
        out.append(f'<circle cx="{L["cx"]}" cy="{L["cy"]}" r="{L["R"] * 1.05:.0f}" fill="{hue[0]}" opacity="{0.2 if dark else 0.13}" filter="url(#b)">{fillanim}</circle>')
        out.append(f'<g id="c" fill="{hue[0]}" fill-opacity="{0.95 if dark else 0.9}">{fillanim}' + "".join(dots) + "</g>")
        if dark:
            out.append(f'<use href="#c" filter="url(#g)" opacity=".7"/>')
    else:
        out.append(f'<g fill="{hue[0]}" fill-opacity="{0.9 if dark else 0.85}">{"".join(dots)}</g>')

    # per-scene text; each group fades in and out on its own clock
    def group(inner, t_in, t_out, j, static_show=False, lift=False):
        if not animated:
            return inner if static_show else ""
        a, b = j * SCENE + t_in, j * SCENE + t_out
        pts = [(0, 0), (a, 0), (a + 0.28, 1), (b, 1), (b + 0.14, 0)]
        pts = [(min(total, tt) / total, v) for tt, v in pts] + [(1, 0)]
        ks = ";".join(kt(p[0]) for p in pts)
        vs = ";".join(str(p[1]) for p in pts)
        mv = ""
        if lift:  # the title rises into place
            tv = ";".join(["0 22" if v == 0 else "0 0" for _, v in pts])
            mv = f'<animateTransform attributeName="transform" type="translate" values="{tv}" keyTimes="{ks}" dur="{total:g}s" repeatCount="indefinite"/>'
        return f'<g opacity="0"><animate attributeName="opacity" values="{vs}" keyTimes="{ks}" dur="{total:g}s" repeatCount="indefinite"/>{mv}{inner}</g>'

    for j, (a, b, _, _, labels, ov) in enumerate(TOPICS):
        col = hue[j]
        title = (f'<text class="t" x="{L["x"]}" y="{L["t1"]}" font-size="{L["tsz"]}">{s6.use(a)}</text>'
                 f'<text class="t" x="{L["x"]}" y="{L["t2"]}" font-size="{L["tsz"]}">{s6.use(b)}</text>')
        out.append(group(title, 0.05, SCENE - 0.12, j, static_show=(j == 0), lift=True))
        for q, lab in enumerate(labels):
            t_a = 0.15 + q * 1.6
            inner = (f'<circle cx="{L["x"] + 4}" cy="{L["label"] - 4}" r="3" fill="{col}"/>'
                     f'<text class="l" x="{L["x"] + 18}" y="{L["label"]}" font-size="13" fill="{col}">{esc(m4.use(lab))}…</text>')
            out.append(group(inner, t_a, t_a + 1.5, j))
        lines = wrap(s4, ov, L["ovsz"], L["ovw"])
        inner = "".join(f'<text class="p" x="{L["x"]}" y="{L["ov"] + i * L["lead"]}" font-size="{L["ovsz"]}">{s4.use(esc(ln))}</text>' for i, ln in enumerate(lines))
        out.append(group(inner, 1.0, SCENE - 0.12, j, static_show=(j == 0)))
    if not animated:
        lab = TOPICS[0][4][1]
        out.append(f'<circle cx="{L["x"] + 4}" cy="{L["label"] - 4}" r="3" fill="{hue[0]}"/>')

    # progress ticks
    for j in range(len(TOPICS)):
        x = L["x"] + j * (L["tickw"] + 8)
        out.append(f'<rect x="{x}" y="{L["ticks"]}" width="{L["tickw"]}" height="2" fill="{T["hair"]}"/>')
        if animated:
            a, b = j * SCENE, (j + 1) * SCENE
            pts = [(0, 0), (a, 0), (a + 0.01, 1), (b - 0.01, 1), (b, 0)]
            pts = [(min(total, tt) / total, v) for tt, v in pts] + [(1, 0)]
            ks = ";".join(kt(p[0]) for p in pts)
            vs = ";".join(str(p[1]) for p in pts)
            out.append(f'<rect x="{x}" y="{L["ticks"]}" width="{L["tickw"]}" height="2" fill="{hue[j]}" opacity="0"><animate attributeName="opacity" values="{vs}" keyTimes="{ks}" dur="{total:g}s" repeatCount="indefinite"/></rect>')
        elif j == 0:
            out.append(f'<rect x="{x}" y="{L["ticks"]}" width="{L["tickw"]}" height="2" fill="{hue[0]}"/>')

    title = "Josh Botha, developer in Sydney. Ask me about my work: web and app design, systems design, data design, AI implementation, finance and BI, medical science."
    return svg_doc(W, H, title, css, "".join(out), fs)


if __name__ == "__main__":
    for theme in THEMES:
        for layout in LAYOUTS:
            for animated in (True, False):
                name = f"work-{layout}-{theme}{'' if animated else '-static'}.svg"
                svg = build(theme, layout, animated)
                (ROOT / "assets" / name).write_text(svg)
                print(f"{name}  {len(svg) / 1024:.0f} KB")
