"""Renders the profile README's SVG slices into assets/.

Every slice is part of one continuous console frame. Run fetch.py first to refresh
data/*.json; this script only reads those files and draws.

Every slice is W wide, a multiple of 40px tall (so the grid lines up across slices),
and draws the same side rails; only the first slice has the top edge and title bar,
only the last one closes the frame.
"""
import base64, datetime, hashlib, html, io, json, math, os, pathlib, re, sys, textwrap

from fontTools import subset
from fontTools.ttLib import TTFont

from themes import THEMES, DEFAULT as DEFAULT_THEME, city_palette

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE / "data"
OUT = ROOT / "assets"
FONT_DIR = HERE / "fonts"
GREEN = "#3fb950"


def _theme_name():
    """--theme NAME / --theme=NAME / PROFILE_THEME, resolved at import time because the colours are module constants."""
    a = sys.argv
    for i, x in enumerate(a):
        if x == "--theme" and i + 1 < len(a):
            return a[i + 1]
        if x.startswith("--theme="):
            return x.split("=", 1)[1]
    return os.environ.get("PROFILE_THEME") or DEFAULT_THEME


THEME = _theme_name()
if THEME not in THEMES:
    sys.exit(f"unknown theme {THEME!r}; choose one of: {', '.join(THEMES)}")
CYAN, MAGENTA = THEMES[THEME]       # "main" and "accent" colours (names kept from the original cyan/magenta design)
CITY = city_palette(CYAN)
W, M = 880, 16            # slice width, transparent side margin (room for the glow)
FL, FR = M, W - M         # frame left / right
X = 52                    # text left edge
e = html.escape


def visible(markup):
    """The characters a piece of SVG markup actually displays (so the font subset never misses one)."""
    return html.unescape(re.sub(r"<[^>]+>", "", markup))


def faces(text, weights=(400, 700)):
    text += "0123456789"
    out = []
    for w in weights:
        f = TTFont(FONT_DIR / f"jetbrains-mono-latin-{w}-normal.woff2", recalcTimestamp=False)  # fixed timestamp keeps output byte-identical between runs
        o = subset.Options(); o.flavor = "woff2"; o.layout_features = []
        s = subset.Subsetter(o); s.populate(text=text); s.subset(f)
        b = io.BytesIO(); f.flavor = "woff2"; f.save(b)
        out.append(f"@font-face{{font-family:'JBM';font-weight:{w};src:url(data:font/woff2;base64,"
                   f"{base64.b64encode(b.getvalue()).decode()}) format('woff2')}}")
    return "".join(out)


BASE_CSS = f"""text{{font-family:'JBM',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:15px}}
.dim{{fill:#8b949e}}.cy{{fill:{CYAN}}}.fg{{fill:#c9d1d9}}.gr{{fill:{GREEN}}}.wh{{fill:#f0fbff}}
@keyframes fadein{{from{{opacity:0;transform:translateX(-6px)}}to{{opacity:1;transform:none}}}}
@keyframes blink{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.35}}}}
.ln{{animation:fadein .35s ease-out both}}
.cursor{{animation:blink 1.05s step-end infinite}}
.dot{{animation:pulse 2s ease-in-out infinite}}"""

DEFS = f"""<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="{CYAN}" stroke-opacity=".06"/></pattern>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
<filter id="g" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="4"/></filter>"""


def slice_svg(h, body, *, title, desc, text, top=False, bottom=False, css="", defs="", weights=(400, 700)):
    assert h % 40 == 0, h
    y0 = M if top else 0
    y1 = h - M if bottom else h
    rails = f"M{FL} {y0}V{y1}M{FR} {y0}V{y1}"
    if top:
        rails += f"M{FL} {y0}H{FR}"
    if bottom:
        rails += f"M{FL} {y1}H{FR}"
    gy0 = y0 if top else -40
    gy1 = y1 if bottom else h + 40
    glow = f"M{FL} {gy0}V{gy1}M{FR} {gy0}V{gy1}" + (f"M{FL} {y0}H{FR}" if top else "") + (f"M{FL} {y1}H{FR}" if bottom else "")
    corners = ""
    if top:
        corners += f'<path d="M{FL-7} {y0+18}V{y0-7}H{FL+18}"/><path d="M{FR-18} {y0-7}H{FR+7}V{y0+18}"/>'
    if bottom:
        corners += f'<path d="M{FL-7} {y1-18}V{y1+7}H{FL+18}"/><path d="M{FR-18} {y1+7}H{FR+7}V{y1-18}"/>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-labelledby="t d">
<title id="t">{e(title)}</title>
<desc id="d">{e(desc)}</desc>
<style>
{faces(text + visible(body), weights)}
{BASE_CSS}
{css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<defs>
{DEFS}
{defs}
</defs>
<path d="{glow}" fill="none" stroke="{CYAN}" stroke-width="3" opacity=".55" filter="url(#glow)"/>
<rect x="{FL}" y="{y0}" width="{FR-FL}" height="{y1-y0}" fill="#03040a"/>
<rect x="{FL}" y="{y0}" width="{FR-FL}" height="{y1-y0}" fill="url(#grid)"/>
{body}
<path d="{rails}" fill="none" stroke="{CYAN}" stroke-width="1.2"/>
<g fill="none" stroke="{CYAN}" stroke-width="2">{corners}</g>
</svg>
'''


def heading(y, name, counter):
    return f'''<text x="{X}" y="{y}" font-weight="700" fill="{CYAN}" filter="url(#g)" opacity=".8" style="font-size:20px">~/</text>
<text x="{X}" y="{y}" font-weight="700" style="font-size:20px"><tspan class="cy">~/</tspan><tspan class="wh">{e(name)}</tspan></text>
<text x="{FR-36}" y="{y}" text-anchor="end" letter-spacing="2" fill="#6e7681" style="font-size:12px">{e(counter)}</text>
<line x1="{X}" y1="{y+14}" x2="{FR-36}" y2="{y+14}" stroke="{CYAN}" stroke-opacity=".4"/>
<line x1="{X}" y1="{y+14}" x2="{X+120}" y2="{y+14}" stroke="{CYAN}" stroke-width="2"/>
<line x1="{X}" y1="{y+14}" x2="{X+120}" y2="{y+14}" stroke="{CYAN}" stroke-width="3" filter="url(#g)"/>'''


def stagger(rows, y0, lh, delay0=0.15, step=0.12):
    """rows: markup strings with {y}, or None for a small spacer. Returns (markup, next_y)."""
    out, y, i = [], y0, 0
    for r in rows:
        if r is None:
            y += 14; continue
        i += 1
        out.append(f'<g class="ln" style="animation-delay:{delay0 + i*step:.2f}s">' + r.replace("{y}", str(y)) + "</g>")
        y += lh
    return "\n".join(out), y


def up40(v):
    return int(math.ceil(v / 40) * 40)


# ─────────────────────────────── header ───────────────────────────────
def build_header():
    bar_left, bar_right = "SYS://SHAMBIX // NODE:JANY", "ONLINE · ALL SYSTEMS NOMINAL"
    name = "JANY MARTELLI"
    lines = ["computer scientist · software engineer · tech professor", "building systems since 2009 at ",
             "open source enthusiast"]
    text = bar_left + bar_right + name + "$ whoami>>" + "".join(lines) + "SHAMBIX"
    h = 360
    css = f"""@keyframes type{{from{{width:0}}}}
@keyframes flicker{{0%{{opacity:0}}10%{{opacity:1}}14%{{opacity:.2}}22%{{opacity:1}}30%{{opacity:.4}}40%,100%{{opacity:1}}}}
@keyframes gm{{0%,92%,100%{{transform:translate(0,0)}}93%{{transform:translate(5px,-1px)}}95%{{transform:translate(-3px,1px)}}97%{{transform:translate(2px,0)}}}}
@keyframes gc{{0%,92%,100%{{transform:translate(0,0)}}93%{{transform:translate(-5px,1px)}}95%{{transform:translate(4px,-1px)}}97%{{transform:translate(-2px,0)}}}}
.typing{{animation:type .7s steps(8) .3s both}}
.name{{animation:flicker .9s linear 1.1s both}}
.gm{{animation:gm 6s linear 2s infinite}}.gc{{animation:gc 6s linear 2s infinite}}"""
    defs = f"""<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" fill-opacity=".2"/></pattern>
<filter id="tglow" x="-5%" y="-40%" width="110%" height="180%"><feGaussianBlur stdDeviation="9"/></filter>
<filter id="sglow" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="3"/></filter>
<clipPath id="typeclip"><rect class="typing" x="{X}" y="80" width="140" height="30"/></clipPath>"""
    dotx = FR - 20 - len(bar_right) * 8.2 - 16
    rows = [f'<text class="fg" x="{X}" y="{{y}}"><tspan class="cy">&gt;&gt;</tspan> {e(lines[0])}</text>',
            f'<text class="fg" x="{X}" y="{{y}}"><tspan class="cy">&gt;&gt;</tspan> {e(lines[1])}<tspan class="cy" font-weight="700">SHAMBIX</tspan></text>',
            f'<text class="fg" x="{X}" y="{{y}}"><tspan class="cy">&gt;&gt;</tspan> {e(lines[2])}</text>']
    desc_lines, _ = stagger(rows, 218, 24, delay0=1.75, step=0.25)
    body = f'''<rect x="{FL}" y="{M}" width="{FR-FL}" height="34" fill="{CYAN}" fill-opacity=".08"/>
<line x1="{FL}" y1="{M+34}" x2="{FR}" y2="{M+34}" stroke="{CYAN}" stroke-opacity=".5"/>
<text x="{FL+16}" y="{M+22}" letter-spacing="1" class="cy" style="font-size:12px">{e(bar_left)}</text>
<text x="{FR-20}" y="{M+22}" letter-spacing="1" class="dim" text-anchor="end" style="font-size:12px">{e(bar_right)}</text>
<circle class="dot" cx="{dotx}" cy="{M+18}" r="4" fill="{GREEN}"/>
<circle class="dot" cx="{dotx}" cy="{M+18}" r="4" fill="{GREEN}" filter="url(#sglow)"/>
<g clip-path="url(#typeclip)"><text x="{X}" y="102" class="dim"><tspan class="gr">$</tspan> whoami</text></g>
<g class="name" font-weight="800" letter-spacing="2" style="font-size:56px">
<text x="{X}" y="172" fill="{CYAN}" opacity=".55" filter="url(#tglow)" style="font-size:56px">{name}</text>
<g class="gm"><text x="{X+3}" y="172" fill="{MAGENTA}" opacity=".75" style="font-size:56px">{name}</text></g>
<g class="gc"><text x="{X-3}" y="172" fill="{CYAN}" opacity=".85" style="font-size:56px">{name}</text></g>
<text x="{X}" y="172" fill="#f0fbff" style="font-size:56px">{name}</text>
</g>
{desc_lines}
<g class="ln" style="animation-delay:2.8s">
<text x="{X}" y="304" class="gr">$</text>
<rect class="cursor" x="{X+18}" y="291" width="10" height="17" fill="{CYAN}"/>
<rect class="cursor" x="{X+18}" y="291" width="10" height="17" fill="{CYAN}" filter="url(#sglow)"/>
</g>
<rect x="{FL}" y="{M+35}" width="{FR-FL}" height="{h-M-35}" fill="url(#scan)"/>'''
    return slice_svg(h, body, title="Jany Martelli",
                     desc="Computer scientist, software engineer and tech professor. "
                          "Building systems since 2009 at Shambix. Open source enthusiast.",
                     text=text, top=True, css=css, defs=defs, weights=(400, 700, 800))


# ─────────────────────────────── footer ───────────────────────────────
def build_footer():
    h = 80
    text = "$ exit connection to Jany-M closed. // EOF"
    body = f'''<text x="{X}" y="30" class="dim"><tspan class="gr">$</tspan> exit</text>
<text x="{X}" y="52" class="dim">connection to <tspan class="cy">Jany-M</tspan> closed. <tspan fill="#484f58">// EOF</tspan></text>'''
    return slice_svg(h, body, title="End of profile", desc="Connection closed.", text=text, bottom=True)



# ────────────────────────────── projects ──────────────────────────────
HW = W // 2   # half-slice width (440, a multiple of 40 so the grid stays aligned)


def half_slice(h, side, body, *, title, desc, text, weights=(400, 700)):
    """Left or right half of a full-width row; only its outer side has a rail."""
    assert h % 40 == 0
    rx = FL if side == "L" else HW - M
    bx0, bx1 = (FL, HW) if side == "L" else (0, HW - M)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{HW}" height="{h}" viewBox="0 0 {HW} {h}" role="img" aria-labelledby="t d">
<title id="t">{e(title)}</title>
<desc id="d">{e(desc)}</desc>
<style>
{faces(text + visible(body), weights)}
{BASE_CSS}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<defs>
{DEFS}
</defs>
<path d="M{rx} -40V{h+40}" fill="none" stroke="{CYAN}" stroke-width="3" opacity=".55" filter="url(#glow)"/>
<rect x="{bx0}" y="0" width="{bx1-bx0}" height="{h}" fill="#03040a"/>
<rect x="{bx0}" y="0" width="{bx1-bx0}" height="{h}" fill="url(#grid)"/>
{body}
<path d="M{rx} 0V{h}" fill="none" stroke="{CYAN}" stroke-width="1.2"/>
</svg>
'''


PROJECTS = [
    dict(slug="patcherly", name="Patcherly", url="https://github.com/Patcherly",
         tag="PRODUCT · ORG", tagc=GREEN, stars=None, stack="AI · Auto-fix · MCP",
         desc="AI that catches and fixes production bugs before you do."),
    dict(slug="repo-visualizer", name="repo-visualizer", url="https://github.com/Jany-M/repo-visualizer",
         tag="OPEN SOURCE", tagc=MAGENTA, stars=11, stack="JavaScript · Git · Visualization",
         desc="A visual representation of the progress history of a repository."),
    dict(slug="airflow-simulator", name="airflow-simulator", url="https://github.com/Jany-M/airflow-simulator",
         tag="OPEN SOURCE", tagc=MAGENTA, stars=9, stack="TypeScript · Simulation",
         desc="Interactive cross-ventilation simulator: draw a floor plan, set the wind and find the best windows to open."),
    dict(slug="more", name="More on GitHub", url="https://github.com/Jany-M?tab=repositories",
         tag="REPOSITORIES", tagc=CYAN, stars=None, stack="PHP · JavaScript · Python",
         desc="WordPress plugins and themes, MCP tools, automation scripts and more."),
]
CARD_H = 200


def build_projects_head():
    h = 120
    body = heading(44, "projects", "// 04") + f'''
<g class="ln" style="animation-delay:.2s"><text x="{X}" y="96" class="dim"><tspan class="gr">$</tspan> ls -l ~/projects</text></g>'''
    return slice_svg(h, body, title="Projects", desc="Projects", text="~/projects// 02$ ls -l")


def build_card(p, side, delay, stars=None):
    p = dict(p, stars=stars.get(p["slug"], p["stars"]) if stars else p["stars"])
    x0 = 52 if side == "L" else 10          # card box, 378 wide, 20px gutter between the two cards
    cw, y0, ch = 378, 12, 176
    pad = 18
    tx = x0 + pad
    cut = 16
    box = f"M{x0} {y0}H{x0+cw-cut}L{x0+cw} {y0+cut}V{y0+ch}H{x0+cut}L{x0} {y0+ch-cut}Z"
    lines = textwrap.wrap(p["desc"], 43)
    assert len(lines) <= 3, lines
    tag_w = len(p["tag"]) * 7.6 + 16
    title_w = len(p["name"]) * 10.2
    desc = "\n".join(f'<text x="{tx}" y="{100 + i*20}" class="fg" style="font-size:13px">{e(l)}</text>' for i, l in enumerate(lines))
    sx = x0 + cw - pad
    star = f'<path transform="translate({sx - len(str(p["stars"]))*7.2 - 20} 158) scale(.55)" d="M10 0l2.9 6.6 7.1.6-5.4 4.7 1.6 7L10 15.2 3.8 18.9l1.6-7L0 7.2l7.1-.6z" fill="#e3b341"/>'
    body = f'''<g class="ln" style="animation-delay:{delay:.2f}s">
<path d="{box}" fill="{CYAN}" fill-opacity=".035"/>
<path d="{box}" fill="none" stroke="{CYAN}" stroke-opacity=".4"/>
<path d="M{x0+cw-cut} {y0}L{x0+cw} {y0+cut}" stroke="{CYAN}" stroke-width="2"/>
<text x="{tx}" y="{y0+34}" font-weight="700" fill="{CYAN}" filter="url(#g)" opacity=".6" style="font-size:17px">{e(p["name"])}</text>
<text x="{tx}" y="{y0+34}" font-weight="700" class="cy" style="font-size:17px">{e(p["name"])}</text>
<path d="M{tx+title_w+11} {y0+31}l8-8M{tx+title_w+13} {y0+23}h6v6" fill="none" stroke="{CYAN}" stroke-width="1.6"/>
<rect x="{tx}" y="{y0+46}" width="{tag_w}" height="18" fill="none" stroke="{p["tagc"]}" stroke-opacity=".8"/>
<text x="{tx+8}" y="{y0+59}" letter-spacing="1" fill="{p["tagc"]}" style="font-size:11px">{e(p["tag"])}</text>
{desc}
<text x="{tx}" y="{y0+158}" class="dim" style="font-size:12px">{e(p["stack"])}</text>
{star if p["stars"] is not None else ""}
{f'<text x="{sx}" y="{y0+158}" text-anchor="end" class="dim" style="font-size:12px">{p["stars"]}</text>' if p["stars"] is not None else ""}
</g>'''
    text = p["name"] + p["tag"] + p["desc"] + p["stack"] + str(p["stars"] or "")
    return half_slice(CARD_H, side, body, title=p["name"],
                      desc=f'{p["name"]}: {p["desc"]} Built with {p["stack"].replace(" · ", ", ")}.' + (f' {p["stars"]} stars.' if p["stars"] is not None else ""), text=text)



# ─────────────────────────────── stats ────────────────────────────────
AMBER, VIOLET = "#e3b341", "#bc8cff"
LANG_POOL = [CYAN, MAGENTA, GREEN, VIOLET, "#2f81f7", AMBER, "#ff7b72", "#39c5cf", "#f778ba"]


def lang_colors(n):
    """n visually distinct colours: main, accent, then the pool, skipping anything too close in hue to a pick."""
    import colorsys
    def hue(c):
        return colorsys.rgb_to_hls(*(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)))[0]
    picked = []
    for c in LANG_POOL:
        if all(min(abs(hue(c) - hue(p)), 1 - abs(hue(c) - hue(p))) > 0.07 for p in picked):
            picked.append(c)
        if len(picked) == n:
            break
    return picked


def fmt(n):
    return "—" if n is None else f"{n:,}"


def tile(x, y, w, h, label, value, sub, delay, pending=False):
    vc = "#484f58" if pending else CYAN
    glow = "" if pending else f'<text x="{x+16}" y="{y+50}" font-weight="700" fill="{CYAN}" filter="url(#g)" opacity=".55" style="font-size:30px">{e(value)}</text>'
    return f'''<g class="ln" style="animation-delay:{delay:.2f}s">
<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{CYAN}" fill-opacity=".035" stroke="{CYAN}" stroke-opacity=".35"/>
<path d="M{x} {y+12}V{y}H{x+12}" fill="none" stroke="{CYAN}" stroke-width="2"/>
<text x="{x+16}" y="{y+22}" letter-spacing="1.5" class="dim" style="font-size:10.5px">{e(label)}</text>
{glow}<text x="{x+16}" y="{y+50}" font-weight="700" fill="{vc}" style="font-size:30px">{e(value)}</text>
<text x="{x+16}" y="{y+h-12}" fill="#6e7681" style="font-size:12px">{e(sub)}</text>
</g>'''


def build_stats(d):
    y = datetime.date.fromisoformat(d["updated"])
    since = datetime.date.fromisoformat(d["created_at"][:10])
    yrs = (y - since).days // 365
    parts = []
    parts.append(heading(44, "stats", "// 02"))
    parts.append(f'<g class="ln" style="animation-delay:.15s"><text x="{X}" y="96" class="dim"><tspan class="gr">$</tspan> gh stats --user Jany-M</text></g>')
    # row 1 — big tiles
    tw, gap, ty, th = 182, 16, 118, 92
    t1 = [("TOTAL STARS", fmt(d["stars"]), f"across {d.get('repo_count', 'all')} repos" if d.get("repo_count") else "across all repos"),
          (f"CONTRIBUTIONS {d['year']}", fmt(d["contributions_year"]), f"{fmt(d['contributions_all'])} all time")
          if "contributions_year" in d else   # older data files only have commit counts
          (f"COMMITS {d['year']}", fmt(d["commits_year"]), f"{fmt(d['commits_all'])} all time"),
          ("PULL REQUESTS", fmt(d["prs"]), f"{fmt(d['prs_merged'])} merged"),
          ("CURRENT STREAK", f"{d['streak_current']}d", f"longest: {d['streak_longest']} days")]
    for i, (lab, val, sub) in enumerate(t1):
        parts.append(tile(X + i * (tw + gap), ty, tw, th, lab, val, sub, .25 + i * .08))
    # row 2 — neofetch list + languages
    ry, rh = ty + th + 16, 150
    lw = 300
    kv = [("followers", fmt(d["followers"])), ("forks", fmt(d["forks"])),
          ("member since", f"{since:%b %Y} ({yrs}y)"), ("repos", fmt(d.get("repo_count")))]
    rows = "\n".join(
        f'<text x="{X+16}" y="{ry+38+i*28}" xml:space="preserve"><tspan class="cy">{e(k)}</tspan><tspan class="dim">{"." * (16 - len(k))}</tspan> <tspan class="fg">{e(v)}</tspan></text>'
        for i, (k, v) in enumerate(kv))
    parts.append(f'''<g class="ln" style="animation-delay:.6s">
<rect x="{X}" y="{ry}" width="{lw}" height="{rh}" fill="{CYAN}" fill-opacity=".035" stroke="{CYAN}" stroke-opacity=".35"/>
<path d="M{X} {ry+12}V{ry}H{X+12}" fill="none" stroke="{CYAN}" stroke-width="2"/>
{rows}
</g>''')
    lx = X + lw + gap
    lwid = (FR - 36) - lx
    langs = sorted(d["languages"].items(), key=lambda kv: -kv[1])
    total = sum(v for _, v in langs)
    top = langs[:5]
    other = total - sum(v for _, v in top)
    items = [(k, v / total) for k, v in top] + ([("Other", other / total)] if other else [])
    cols = lang_colors(len(top)) + ["#6e7681"]   # one distinct colour per language, grey for Other
    bx, by, bw = lx + 16, ry + 42, lwid - 32
    segs, cx = [], bx
    for (k, p), c in zip(items, cols):
        w = bw * p
        segs.append(f'<rect x="{cx:.1f}" y="{by}" width="{max(w-2,1):.1f}" height="8" fill="{c}"/>')
        segs.append(f'<rect x="{cx:.1f}" y="{by}" width="{max(w-2,1):.1f}" height="8" fill="{c}" filter="url(#g)" opacity=".6"/>')
        cx += w
    legend = []
    for i, ((k, p), c) in enumerate(zip(items, cols)):
        col, row = i % 2, i // 2
        lxx = bx + col * (bw / 2)
        lyy = by + 36 + row * 26
        legend.append(f'<rect x="{lxx}" y="{lyy-9}" width="9" height="9" fill="{c}"/>'
                      f'<text x="{lxx+18}" y="{lyy}" class="fg" style="font-size:13px">{e(k)}</text>'
                      f'<text x="{lxx + bw/2 - 24}" y="{lyy}" text-anchor="end" class="dim" style="font-size:13px">{p*100:.1f}%</text>')
    parts.append(f'''<g class="ln" style="animation-delay:.7s">
<rect x="{lx}" y="{ry}" width="{lwid}" height="{rh}" fill="{CYAN}" fill-opacity=".035" stroke="{CYAN}" stroke-opacity=".35"/>
<path d="M{lx} {ry+12}V{ry}H{lx+12}" fill="none" stroke="{CYAN}" stroke-width="2"/>
<text x="{lx+16}" y="{ry+24}" letter-spacing="1.5" class="dim" style="font-size:10.5px">TOP LANGUAGES</text>
<rect x="{bx}" y="{by}" width="{bw}" height="8" fill="#11161d"/>
{"".join(segs)}
{"".join(legend)}
</g>''')
    # row 3 — DEV Community (tiles without data are left out; the row hides if all are missing)
    dv = d.get("dev") or {}
    t3 = [(lab, dv.get(k)) for lab, k in (("ARTICLES", "articles"), ("REACTIONS", "reactions"), ("COMMENTS", "comments"),
                                          ("VIEWS", "views"), ("DEV FOLLOWERS", "followers"))]
    t3 = [(lab, v) for lab, v in t3 if v is not None]
    fy = ry + rh + 30
    if t3:
        dy = ry + rh + 34
        parts.append(f'<g class="ln" style="animation-delay:.8s"><text x="{X}" y="{dy}" class="dim"><tspan class="gr">$</tspan> dev stats --user Jany-M</text></g>')
        n = len(t3)
        dw = (FR - 36 - X - (n - 1) * 12) / n
        for i, (lab, val) in enumerate(t3):
            parts.append(tile(X + i * (dw + 12), dy + 16, dw, 76, lab, fmt(val), "", .9 + i * .06))
        fy = dy + 16 + 76 + 30
    parts.append(f'<text x="{FR-36}" y="{fy}" text-anchor="end" fill="#484f58" style="font-size:11px">// last sync {d["updated"]}</text>')
    h = up40(fy + 16)
    text = "".join(str(x) for x in ["~/stats// 02$ gh stats --user Jany-M dev stats", "".join(p for p in parts)])
    text = re.sub(r"<[^>]+>", "", text) + "0123456789,—%.★()d"
    activity = (f"{d['contributions_year']} contributions in {d['year']}, {d['contributions_all']} all time"
                if "contributions_year" in d else f"{d['commits_year']} commits in {d['year']}, {d['commits_all']} all time")
    desc = (f"GitHub stats: {d['stars']} total stars; {activity}; "
            f"{d['prs']} pull requests ({d['prs_merged']} merged); current streak {d['streak_current']} days, longest {d['streak_longest']}; "
            f"{d['followers']} followers; {d['forks']} forks; member since {since:%B %Y}. "
            "Top languages: " + ", ".join(f"{k} {p*100:.1f}%" for k, p in items) + "."
            + ("" if not t3 else " DEV Community: " + ", ".join(f"{fmt(v)} {lab.lower()}" for lab, v in t3) + "."))
    return slice_svg(h, "\n".join(parts), title="Stats", desc=desc, text=html.unescape(text))


# ─────────────────────────────── stack ────────────────────────────────
STACK = [
    ("languages", ["TypeScript", "JavaScript", "Python", "Dart", "PHP", "Java", "PowerShell"]),
    ("platforms", ["React", "Node.js", "Next.js", "FastAPI", "Flutter", "Electron"]),
    ("also", ["Android", "Express", "Expo", "DevOps", "Render", "Vercel"]),
    ("data", ["MongoDB", "MySQL", "Redis", "GraphQL"]),
    ("ai", ["Local LLMs", "MCP", "RAG", "Agents", "PyTorch", "OpenCV"]),
    ("infra", ["AWS", "Linux", "Docker", "Cloudflare", "Netlify", "GitHub Actions"]),
]


def build_stack():
    parts = [heading(44, "stack", "// 05"),
             f'<g class="ln" style="animation-delay:.15s"><text x="{X}" y="96" class="dim"><tspan class="gr">$</tspan> scan --loadout --top-level</text></g>']
    y, rowh = 126, 44
    cw = 0.6 * 13          # char advance at 13px
    for r, (cat, items) in enumerate(STACK):
        parts.append(f'<g class="ln" style="animation-delay:{.25 + r*.1:.2f}s">')
        parts.append(f'<text x="{X}" y="{y+20}" class="dim" style="font-size:13px">{e(cat)}</text>')
        parts.append(f'<text x="{X+104}" y="{y+20}" class="cy" style="font-size:13px">›</text>')
        x = X + 124
        for it in items:
            w = len(it) * cw + 26
            if x + w > FR - 36:           # wrap to a second line inside the same row
                x = X + 124
                y += 40
                parts.append("</g>" + f'<g class="ln" style="animation-delay:{.25 + r*.1:.2f}s">')
            parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="30" fill="{CYAN}" fill-opacity=".06" stroke="{CYAN}" stroke-opacity=".55"/>')
            parts.append(f'<path d="M{x:.1f} {y+8}V{y}H{x+8:.1f}" fill="none" stroke="{CYAN}" stroke-width="2"/>')
            parts.append(f'<text x="{x+13:.1f}" y="{y+20}" font-weight="700" class="cy" style="font-size:13px">{e(it)}</text>')
            x += w + 10
        parts.append("</g>")
        y += rowh
    h = up40(y + 10)
    text = "~/stack// 05$ scan --loadout --top-level›" + "".join(c + "".join(i) for c, i in STACK)
    desc = "Tech stack. " + " ".join(f"{c}: {', '.join(i)}." for c, i in STACK)
    return slice_svg(h, "\n".join(parts), title="Tech stack", desc=desc, text=text)


# ─────────────────────────────── writing ──────────────────────────────
HEART = "M8 14.2 6.9 13.2C3 9.7.5 7.4.5 4.6.5 2.3 2.3.5 4.6.5c1.3 0 2.5.6 3.4 1.6C8.9 1.1 10.1.5 11.4.5c2.3 0 4.1 1.8 4.1 4.1 0 2.8-2.5 5.1-6.4 8.6z"
BUBBLE = "M1.5 1.5h13v9h-7l-3.5 3v-3h-2.5z"


def build_writing_head():
    body = heading(44, "writing", "// 06") + f'''
<g class="ln" style="animation-delay:.15s"><text x="{X}" y="96" class="dim"><tspan class="gr">$</tspan> tail -n 5 ~/shambix.com/blog.log <tspan fill="#484f58"># auto-updated</tspan></text></g>'''
    return slice_svg(120, body, title="Writing", desc="Latest articles on the Shambix blog",
                     text="~/writing// 06$ tail -n 5 ~/shambix.com/blog.log # auto-updated")


def build_article_row(a, i):
    date = a["published_at"][:10]
    title = a["title"]
    maxc = 50
    shown = title if len(title) <= maxc else title[:maxc - 1].rstrip(" .,:;") + "…"
    tx = X + 112
    rx = FR - 36
    cat = a.get("category", "")
    ax = rx - 10
    body = f'''<g class="ln" style="animation-delay:{.2 + i*.08:.2f}s">
<rect x="{X-10}" y="4" width="{rx - X + 20}" height="32" fill="{CYAN}" fill-opacity="{'.04' if i % 2 == 0 else '0'}"/>
<text x="{X}" y="25" class="dim" style="font-size:13px">{date}</text>
<text x="{X+94}" y="25" class="cy" style="font-size:13px">›</text>
<text x="{tx}" y="25" class="fg" style="font-size:14px">{e(shown)}</text>
<text x="{ax-20}" y="25" text-anchor="end" fill="{MAGENTA}" style="font-size:12px">{e(cat)}</text>
<path d="M{ax-6} 25l8-8M{ax-4} 17h6v6" fill="none" stroke="{CYAN}" stroke-width="1.5"/>
</g>'''
    text = date + "›" + shown + cat
    return slice_svg(40, body, title=title,
                     desc=f"{title}. Published {date}. Category: {cat}.", text=text)


def build_writing_more():
    body = f'''<g class="ln" style="animation-delay:.7s">
<text x="{X}" y="26" style="font-size:13px"><tspan class="gr">&gt;&gt;</tspan><tspan class="cy"> read all articles on the Shambix blog</tspan></text>
<path d="M{X+322} 26l8-8M{X+324} 18h6v6" fill="none" stroke="{CYAN}" stroke-width="1.5"/>
</g>'''
    return slice_svg(40, body, title="All articles", desc="Read all articles on DEV Community",
                     text=">> read all articles on the Shambix blog")


# ──────────────────────────────── links ───────────────────────────────
LINKS = [
    ("linkedin", "LinkedIn", "in/janymartelli", "https://www.linkedin.com/in/janymartelli"),
    ("shambix", "Shambix", "shambix.com", "https://www.shambix.com"),
]
ICONS = json.load(open(HERE / "icons.json"))
SEG = W // 5     # 176 px per button slice
BTN_W, BTN_GAP = 124, 39  # buttons line up with the text column (x = 52 … 828)


def icon_markup(key, x, y, size=18):
    if key == "linkedin":   # simple generic "in" glyph (LinkedIn isn't in Simple Icons)
        return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="3" fill="{CYAN}"/>'
                f'<text x="{x + size/2}" y="{y + size - 4.5}" text-anchor="middle" font-weight="700" fill="#03040a" style="font-size:12px">in</text>')
    if key == "shambix":
        return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="3" fill="{CYAN}"/>'
                f'<text x="{x + size/2}" y="{y + size - 4}" text-anchor="middle" font-weight="700" fill="#03040a" style="font-size:13px">S</text>')
    d = ICONS[key]
    return f'<path transform="translate({x} {y}) scale({size/24})" d="{d}" fill="{CYAN}"/>'


def build_link_button(k):
    key, label, handle, url = LINKS[k]
    h = 80
    x0 = SEG * k                       # this slice's position inside the full-width row
    lx = X + k * (BTN_W + BTN_GAP) - x0
    first, last = k == 0, False
    bg0 = FL - x0 if first else 0
    bg1 = FR - x0 if last else SEG
    rails = (f"M{FL - x0} 0V{h}" if first else "") + (f"M{FR - x0} 0V{h}" if last else "")
    glow = (f"M{FL - x0} -40V{h+40}" if first else "") + (f"M{FR - x0} -40V{h+40}" if last else "")
    by, bh, cut = 12, 56, 12
    box = f"M{lx} {by}H{lx+BTN_W-cut}L{lx+BTN_W} {by+cut}V{by+bh}H{lx}Z"
    text = label + handle + "inS"
    body = f'''<g class="ln" style="animation-delay:{.25 + k*.08:.2f}s">
<path d="{box}" fill="{CYAN}" fill-opacity=".05"/>
<path d="{box}" fill="none" stroke="{CYAN}" stroke-opacity=".55"/>
<path d="M{lx+BTN_W-cut} {by}L{lx+BTN_W} {by+cut}" stroke="{CYAN}" stroke-width="2"/>
<g filter="url(#g)" opacity=".5">{icon_markup(key, lx+12, by+11)}</g>
{icon_markup(key, lx+12, by+11)}
<text x="{lx+38}" y="{by+25}" font-weight="700" class="cy" style="font-size:13px">{e(label)}</text>
<text x="{lx+12}" y="{by+46}" class="dim" style="font-size:10px">{e(handle)}</text>
</g>'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{SEG}" height="{h}" viewBox="0 0 {SEG} {h}" role="img" aria-labelledby="t d">
<title id="t">{e(label)}</title>
<desc id="d">{e(label)}: {e(url)}</desc>
<style>
{faces(text + visible(body))}
{BASE_CSS}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<defs>
<pattern id="grid" x="{(-x0) % 40}" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="{CYAN}" stroke-opacity=".06"/></pattern>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
<filter id="g" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="4"/></filter>
</defs>
{f'<path d="{glow}" fill="none" stroke="{CYAN}" stroke-width="3" opacity=".55" filter="url(#glow)"/>' if glow else ""}
<rect x="{bg0}" y="0" width="{bg1-bg0}" height="{h}" fill="#03040a"/>
<rect x="{bg0}" y="0" width="{bg1-bg0}" height="{h}" fill="url(#grid)"/>
{body}
{f'<path d="{rails}" fill="none" stroke="{CYAN}" stroke-width="1.2"/>' if rails else ""}
</svg>
'''

def build_link_filler(first_slot):
    h, x0 = 80, SEG * first_slot
    w = W - x0
    rx = FR - x0
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-hidden="true">
<defs>
<pattern id="grid" x="{(-x0) % 40}" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="{CYAN}" stroke-opacity=".06"/></pattern>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
</defs>
<path d="M{rx} -40V{h+40}" fill="none" stroke="{CYAN}" stroke-width="3" opacity=".55" filter="url(#glow)"/>
<rect x="0" y="0" width="{rx}" height="{h}" fill="#03040a"/>
<rect x="0" y="0" width="{rx}" height="{h}" fill="url(#grid)"/>
<path d="M{rx} 0V{h}" fill="none" stroke="{CYAN}" stroke-width="1.2"/>
</svg>
'''


# ─────────────────────────── contribution city ────────────────────────

CITY_TW, CITY_TH = 25, 12.5                  # iso tile width / height
CITY_OX, CITY_OY = 152.5, 262                # grid origin inside the 880-wide slice
CITY_HMAX = 118                              # tallest building, px
ROOFS = CITY["roofs"]   # dark → bright shades of the main colour
WIN_ON, WIN_ON_SIDE, WIN_OFF = CITY["win_on"], CITY["win_side"], "#111827"


def _shade(hexc, f):
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c * f))) for c in (r, g, b))


def _p(x, y):
    return f"{x:.1f},{y:.1f}"


def _rng(seed):
    """Tiny deterministic PRNG, so the same data always draws the same windows."""
    state = int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16)
    while True:
        state = (state * 6364136223846793005 + 1442695040888963407) % 2**64
        yield (state >> 11) / 2**53


def _levels(counts):
    """GitHub-style quartile thresholds over the non-zero days."""
    nz = sorted(c for c in counts if c > 0)
    if not nz:
        return [1, 1, 1]
    q = lambda f: nz[min(len(nz) - 1, int(len(nz) * f))]
    return [q(.25), q(.5), q(.75)]


def build_city(calendar, updated):
    days = [(datetime.date.fromisoformat(d), n) for d, n in calendar]
    counts = [n for _, n in days]
    total, peak = sum(counts), max(counts) if counts else 0
    lv = _levels(counts)
    rnd = _rng(f"{updated}-{total}")
    start = days[0][0]

    cells = []
    for d, n in days:
        idx = (d - start).days
        cells.append((idx // 7, (d.weekday() + 1) % 7, n))      # week column, Sunday = 0
    cells.sort(key=lambda c: (c[0] + c[1], c[0]))                 # back to front

    shapes, flick = [], 0
    for w, dow, n in cells:
        cx = CITY_OX + (w - dow) * CITY_TW / 2
        cy = CITY_OY + (w + dow) * CITY_TH / 2
        L, R = (cx - CITY_TW / 2, cy), (cx + CITY_TW / 2, cy)
        T, B = (cx, cy - CITY_TH / 2), (cx, cy + CITY_TH / 2)
        if n == 0:
            shapes.append(f'<path d="M{_p(*T)}L{_p(*R)}L{_p(*B)}L{_p(*L)}Z" fill="#161b22" stroke="#0d1117" stroke-width=".6"/>')
            continue
        h = 8 + (CITY_HMAX - 8) * math.sqrt(n / peak)
        level = sum(n > t for t in lv)
        Tu, Ru, Bu, Lu = [(x, y - h) for x, y in (T, R, B, L)]
        shapes.append(f'<path d="M{_p(*L)}L{_p(*B)}L{_p(*Bu)}L{_p(*Lu)}Z" fill="{CITY["wall_l"]}"/>'
                      f'<path d="M{_p(*B)}L{_p(*R)}L{_p(*Ru)}L{_p(*Bu)}Z" fill="{CITY["wall_r"]}"/>'
                      f'<path d="M{_p(*Tu)}L{_p(*Ru)}L{_p(*Bu)}L{_p(*Lu)}Z" fill="{ROOFS[level]}"/>')
        on, side, off, fl = [], [], [], []
        for face, (a, b) in (("l", (L, B)), ("r", (B, R))):
            for r in range(int((h - 6) // 7)):
                v0 = 5 + r * 7
                for u0 in (.18, .58):
                    lit = next(rnd) < .55
                    if not lit and next(rnd) < .5:
                        continue
                    pts = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u - v)
                           for u, v in ((u0, v0), (u0 + .26, v0), (u0 + .26, v0 + 3.2), (u0, v0 + 3.2))]
                    seg = "M" + "L".join(_p(*q) for q in pts) + "Z"
                    if not lit:
                        off.append(seg)
                    elif next(rnd) < .03:
                        fl.append((seg, face))
                    else:
                        (on if face == "l" else side).append(seg)
        if off:
            shapes.append(f'<path d="{"".join(off)}" fill="{WIN_OFF}"/>')
        if on:
            shapes.append(f'<path d="{"".join(on)}" fill="{WIN_ON}"/>')
        if side:
            shapes.append(f'<path d="{"".join(side)}" fill="{WIN_ON_SIDE}"/>')
        for seg, face in fl:
            flick += 1
            shapes.append(f'<path class="f{flick % 3}" d="{seg}" fill="{WIN_ON if face == "l" else WIN_ON_SIDE}"/>')

    # night sky in the empty top-right corner: stars, moon, a plane crossing
    stars = []
    for i in range(46):
        x, y = 470 + next(rnd) * 350, 118 + next(rnd) * 150
        if x > 700 and y < 215:           # keep the moon clear
            continue
        cls = f' class="s{i % 3}"' if i % 3 == 0 else ""
        stars.append(f'<circle{cls} cx="{x:.1f}" cy="{y:.1f}" r="{(.6, .8, 1.1)[i % 3]}" fill="#c9d1d9" opacity="{.35 + next(rnd) * .5:.2f}"/>')
    busiest_d, busiest_n = max(days, key=lambda t: t[1]) if days else (None, 0)
    info = [f'<tspan class="cy" font-weight="700">{total:,}</tspan> contributions · last 365 days',
            f'busiest day <tspan class="fg">{busiest_d:%b} {busiest_d.day}</tspan> · {busiest_n}' if busiest_n else "",
            f'{sum(1 for n in counts if n)} active days']
    info_svg = "".join(f'<text x="{FR-36}" y="{300 + i*20}" text-anchor="end" class="dim" style="font-size:12px">{t}</text>'
                       for i, t in enumerate(info) if t)
    legend = "".join(f'<rect x="{X + 52 + i*16}" y="{642}" width="11" height="11" fill="{c}"/>'
                     for i, c in enumerate(["#161b22"] + ROOFS))
    body = heading(44, "contribution-city", "// 03") + f'''
<g class="ln" style="animation-delay:.15s"><text x="{X}" y="96" class="dim"><tspan class="gr">$</tspan> render-city --last 365d <tspan fill="#484f58"># one building per day</tspan></text></g>
<g>{"".join(stars)}</g>
<circle cx="{FR-80}" cy="{160}" r="40" fill="url(#moonglow)"/>
<circle cx="{FR-80}" cy="{160}" r="14" fill="#e6edf3"/>
<circle cx="{FR-74}" cy="{155}" r="12.5" fill="#03040a"/>
<g class="plane"><g transform="translate(0 132)"><rect x="0" y="0" width="14" height="2" rx="1" fill="#484f58"/><circle class="bl" cx="0" cy="1" r="1.6" fill="#ff7b72"/><circle class="bl" cx="14" cy="1" r="1.6" fill="#f0f6fc" style="animation-delay:.7s"/></g></g>
{info_svg}
{"".join(shapes)}
<text x="{X}" y="{652}" class="dim" style="font-size:11px">quiet</text>{legend}<text x="{X + 52 + 5*16 + 6}" y="{652}" class="dim" style="font-size:11px">skyscraper</text>'''
    css = f"""@keyframes tw{{0%,100%{{opacity:.9}}50%{{opacity:.15}}}}
@keyframes fl{{0%,40%,100%{{opacity:1}}45%,60%{{opacity:.1}}}}
@keyframes blink{{0%,90%,100%{{opacity:0}}93%{{opacity:1}}}}
@keyframes fly{{from{{transform:translate({FL - 40}px,0)}}to{{transform:translate({FR + 40}px,-30px)}}}}
.s0{{animation:tw 3s infinite}}
.f0{{animation:fl 5s infinite}}.f1{{animation:fl 7s infinite 2s}}.f2{{animation:fl 9s infinite 4s}}
.plane{{animation:fly 26s linear infinite}}.bl{{animation:blink 1.4s infinite}}"""
    defs = f'<radialGradient id="moonglow"><stop offset="0" stop-color="#f0f6fc" stop-opacity=".22"/><stop offset="1" stop-color="#f0f6fc" stop-opacity="0"/></radialGradient>'
    desc = (f"Contribution city: an isometric night skyline with one building per day of the last year, "
            f"taller and brighter for busier days. {total:,} contributions"
            + (f", busiest day {busiest_d:%B} {busiest_d.day} with {busiest_n}" if busiest_n else "") + ".")
    return slice_svg(680, body, title="Contribution city", desc=desc,
                     text="~/contribution-city// 03$ render-city --last 365d # one building per dayquietskyscraper",
                     css=css, defs=defs)


# ──────────────────── contribution city, variation 2: concentric ────────────────────
MAX_STREETS = 12
CAR_COLORS = [CYAN, MAGENTA, "#3fb950", "#bc8cff", "#2f81f7", "#e3b341", "#ff7b72", "#39c5cf", "#f778ba", "#9be9a8", "#ffa657", "#79c0ff"]


def build_city_concentric(calendar, repos, updated):
    """Newest day in the middle, older days spiralling outward (same building logic as the strip).
    One ring road per repo contributed to (random radii, the outermost one wraps the city),
    street lamps along the roads and one car with headlights per repo driving its road."""
    import random
    days = sorted(((datetime.date.fromisoformat(d), n) for d, n in calendar), key=lambda t: t[0], reverse=True)
    counts = [n for _, n in days]
    total, peak = sum(counts), max(counts) if counts else 0
    lv = _levels(counts)
    rnd = _rng(f"concentric-{updated}-{total}")
    rr = random.Random(f"streets-{updated}-{total}")

    repos = sorted(repos, key=lambda r: -r["count"])[:MAX_STREETS]
    N = len(repos)

    # ── ring layout: radius r (Chebyshev distance from the centre) is either a block of buildings or a street
    r0 = 0
    while (2 * r0 + 1) ** 2 < len(days):
        r0 += 1
    wraps = max(1, N // 4) if N else 0              # roads that wrap around the finished city
    inner_n = N - wraps
    pool = list(range(1, r0 + inner_n + 1))
    street_r = set()
    while len(street_r) < inner_n and pool:         # inner roads: random radii, kept apart where possible
        c = rr.choice(pool)
        street_r.add(c)
        pool = [p for p in pool if abs(p - c) > 1]
    if len(street_r) < inner_n:
        rest = [p for p in range(1, r0 + inner_n + 1) if p not in street_r]
        street_r |= set(rr.sample(rest, min(inner_n - len(street_r), len(rest))))
    assigned, idx, lastb = {}, 0, 0                 # (gx, gy) -> day index
    plot_extra = []                                 # unfilled tiles of the last (partial) ring: empty plots
    r = 0
    while idx < len(days):
        if r in street_r:
            r += 1
            continue
        ring = [(0, 0)] if r == 0 else (
            [(x, -r) for x in range(-r, r)] + [(r, y) for y in range(-r, r)] +
            [(x, r) for x in range(r, -r, -1)] + [(-r, y) for y in range(r, -r, -1)])
        for t in ring:
            if idx < len(days):
                assigned[t] = idx
                idx += 1
            else:
                plot_extra.append(t)
        lastb = r
        r += 1
    w = lastb + 1                                   # wrap roads go just outside the last building ring
    while len(street_r) < N:
        if w not in street_r:
            street_r.add(w)
        w += 2
    R = max(max(street_r, default=0), lastb)
    side = 2 * R + 1
    TW = min(22.0, 800.0 / side)
    TH = TW / 2
    s = TW / 25
    HMAX = TW * 3.6
    OX = W / 2
    top_pad = 138 + max(0, HMAX - (R - lastb) * TH)
    OY = top_pad + (R + .5) * TH
    h = up40(OY + (R + .5) * TH + 74 + M)

    def P(gx, gy):
        return OX + (gx - gy) * TW / 2, OY + (gx + gy) * TH / 2

    def pt(gx, gy):
        x, y = P(gx, gy)
        return f"{x:.1f},{y:.1f}"

    def diamond(rad):                               # square ring outline at radius `rad` (grid units)
        return "M" + "L".join(pt(a, b) for a, b in ((-rad, -rad), (rad, -rad), (rad, rad), (-rad, rad))) + "Z"

    # ── ground, streets
    ground = f'<path d="{diamond(R + .5)}" fill="#070b13" stroke="{CYAN}" stroke-opacity=".35"/>'
    roads = "".join(f'<path d="{diamond(sr + .5)}{diamond(sr - .5)}" fill-rule="evenodd" fill="#101624"/>' for sr in sorted(street_r))
    road_edges = "".join(f'<path d="{diamond(sr + .5)}{diamond(sr - .5)}" fill="none" stroke="{CYAN}" stroke-opacity=".18" stroke-width=".6"/>'
                         for sr in sorted(street_r))
    centre_lines = (f'<path d="{"".join(diamond(sr) for sr in sorted(street_r))}" fill="none" stroke="{MAGENTA}" stroke-opacity=".45" '
                    f'stroke-width=".8" stroke-dasharray="{3*s+1:.1f} {3*s+1:.1f}"/>') if street_r else ""

    def tile(gx, gy):
        c = P(gx, gy)
        return f"M{c[0]:.1f},{c[1]-TH/2:.1f}L{c[0]+TW/2:.1f},{c[1]:.1f}L{c[0]:.1f},{c[1]+TH/2:.1f}L{c[0]-TW/2:.1f},{c[1]:.1f}Z"
    plots = f'<path d="{"".join(tile(*t) for t in list(assigned) + plot_extra)}" fill="#161b22" stroke="#0d1117" stroke-width=".5"/>'

    # ── buildings + lamps, painter's order by depth
    items = []   # (depth, tie, svg)
    for (gx, gy), di in assigned.items():
        d, n = days[di]
        if n == 0:
            continue
        cx, cy = P(gx, gy)
        hh = 6 + (HMAX - 6) * math.sqrt(n / peak)
        level = sum(n > t for t in lv)
        L, Rt = (cx - TW / 2, cy), (cx + TW / 2, cy)
        T, B = (cx, cy - TH / 2), (cx, cy + TH / 2)
        Tu, Ru, Bu, Lu = [(x, y - hh) for x, y in (T, Rt, B, L)]
        out = [f'<path d="M{_p(*L)}L{_p(*B)}L{_p(*Bu)}L{_p(*Lu)}Z" fill="{CITY["wall_l"]}"/>'
               f'<path d="M{_p(*B)}L{_p(*Rt)}L{_p(*Ru)}L{_p(*Bu)}Z" fill="{CITY["wall_r"]}"/>'
               f'<path d="M{_p(*Tu)}L{_p(*Ru)}L{_p(*Bu)}L{_p(*Lu)}Z" fill="{ROOFS[level]}"/>']
        on, side_on, off = [], [], []
        for face, (a, b) in (("l", (L, B)), ("r", (B, Rt))):
            for rrow in range(int((hh - 3) // 5)):
                v0 = 3 + rrow * 5
                for u0 in (.2, .58):
                    lit = next(rnd) < .5
                    if not lit and next(rnd) < .5:
                        continue
                    pts = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u - v)
                           for u, v in ((u0, v0), (u0 + .24, v0), (u0 + .24, v0 + 2.4), (u0, v0 + 2.4))]
                    seg = "M" + "L".join(_p(*q) for q in pts) + "Z"
                    (off if not lit else on if face == "l" else side_on).append(seg)
        if off:
            out.append(f'<path d="{"".join(off)}" fill="{WIN_OFF}"/>')
        if on:
            out.append(f'<path d="{"".join(on)}" fill="{WIN_ON}"/>')
        if side_on:
            out.append(f'<path d="{"".join(side_on)}" fill="{WIN_ON_SIDE}"/>')
        items.append((gx + gy, gx, "".join(out)))

    lamp_pos = []
    for sr in sorted(street_r):
        step = 6
        k0 = rr.randrange(step)
        ring = [(x, -sr) for x in range(-sr, sr)] + [(sr, y) for y in range(-sr, sr)] + \
               [(x, sr) for x in range(sr, -sr, -1)] + [(-sr, y) for y in range(sr, -sr, -1)]
        for i, (tx, ty) in enumerate(ring):
            if (i + k0) % step == 0:
                ox = .42 if tx == sr else -.42 if tx == -sr else 0
                oy = .42 if ty == sr else -.42 if ty == -sr else 0
                lamp_pos.append((tx + ox, ty + oy))
    for i, (gx, gy) in enumerate(lamp_pos):
        x, y = P(gx, gy)
        ph = 8 * s + 2
        cls = f' class="lf{i % 3}"' if i % 5 == 0 else ""
        items.append((gx + gy + .01, gx,
                      f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{5*s+2:.1f}" ry="{2.5*s+1:.1f}" fill="#ffd98a" opacity=".13"/>'
                      f'<path d="M{x:.1f},{y:.1f}V{y-ph:.1f}" stroke="#4b5563" stroke-width=".9"/>'
                      f'<circle{cls} cx="{x:.1f}" cy="{y-ph:.1f}" r="1.3" fill="#ffe9b0"/>'
                      f'<circle cx="{x:.1f}" cy="{y-ph:.1f}" r="4.5" fill="url(#lamp)"/>'))
    items.sort(key=lambda t: (t[0], t[1]))

    # ── cars: one per repo, each driving its own street (cars sit under the buildings in the draw order,
    #    so a building in front of a road hides the car, like in a real isometric view)
    cars = []
    order = sorted(street_r)
    rr.shuffle(order)
    for i, repo in enumerate(repos):
        sr = order[i]
        ccw = rr.random() < .5
        rc = min(1.3, sr * .45)
        a = (lambda gx, gy: (gy, gx)) if ccw else (lambda gx, gy: (gx, gy))
        segs = [("M", [(-sr + rc, -sr)]), ("L", [(sr - rc, -sr)]), ("Q", [(sr, -sr), (sr, -sr + rc)]), ("L", [(sr, sr - rc)]),
                ("Q", [(sr, sr), (sr - rc, sr)]), ("L", [(-sr + rc, sr)]), ("Q", [(-sr, sr), (-sr, sr - rc)]),
                ("L", [(-sr, -sr + rc)]), ("Q", [(-sr, -sr), (-sr + rc, -sr)])]
        path = "".join(c + " ".join(pt(*a(gx, gy)) for gx, gy in ps) for c, ps in segs) + "Z"
        length = sum(math.dist(P(*a(*p0)), P(*a(*p1))) for p0, p1 in
                     (((-sr, -sr), (sr, -sr)), ((sr, -sr), (sr, sr)), ((sr, sr), (-sr, sr)), ((-sr, sr), (-sr, -sr))))
        dur = length / (16 + 14 * rr.random())
        begin = -dur * rr.random()
        col = CAR_COLORS[i % len(CAR_COLORS)]
        cars.append(f'<g><animateMotion dur="{dur:.1f}s" begin="{begin:.1f}s" repeatCount="indefinite" rotate="auto" path="{path}"/>'
                    f'<g transform="scale({max(.75, TW / 17):.2f})">'
                    f'<polygon points="5,-1.4 5,1.4 26,6.5 26,-6.5" fill="url(#beam)"/>'
                    f'<rect x="-5" y="-2.3" width="10" height="4.6" rx="1.5" fill="{col}"/>'
                    f'<rect x="-1.8" y="-1.7" width="4.4" height="3.4" rx=".9" fill="#03040a" opacity=".55"/>'
                    f'<circle cx="5" cy="-1.5" r=".95" fill="#fff6d6"/><circle cx="5" cy="1.5" r=".95" fill="#fff6d6"/>'
                    f'<rect x="-5.3" y="-1.9" width=".9" height="1.1" fill="#ff3b3b"/><rect x="-5.3" y=".8" width=".9" height="1.1" fill="#ff3b3b"/>'
                    f'</g></g>')

    # ── sky: stars + moon (outside the map diamond), info block, legend
    stars = []
    for i in range(70):
        x, y = 40 + next(rnd) * (W - 80), 110 + next(rnd) * (OY - 110)
        if abs(x - OX) / ((R + .5) * TW + 14) + abs(y - OY) / ((R + .5) * TH + 14) < 1 or (x > 570 and y < 215) or (x < 170 and y < 215):
            continue
        cl = f' class="s{i % 3}"' if i % 3 == 0 else ""
        stars.append(f'<circle{cl} cx="{x:.1f}" cy="{y:.1f}" r="{(.6, .8, 1.1)[i % 3]}" fill="#c9d1d9" opacity="{.35 + next(rnd) * .5:.2f}"/>')
    busiest_d, busiest_n = max(days, key=lambda t: t[1]) if days else (None, 0)
    named = [r["name"] for r in repos if r.get("name")]
    info = [f'<tspan class="cy" font-weight="700">{total:,}</tspan> contributions · last 365 days',
            f'busiest day <tspan class="fg">{busiest_d:%b} {busiest_d.day}</tspan> · {busiest_n}' if busiest_n else "",
            f'<tspan class="cy" font-weight="700">{N}</tspan> repos · one street and one car each']
    info_svg = "".join(f'<text x="{FR-36}" y="{150 + i*20}" text-anchor="end" class="dim" style="font-size:12px">{t}</text>'
                       for i, t in enumerate(info) if t)
    ly = h - M - 24
    legend = "".join(f'<rect x="{X + 52 + i*16}" y="{ly-10}" width="11" height="11" fill="{c}"/>'
                     for i, c in enumerate(["#161b22"] + ROOFS))
    body = heading(44, "contribution-city", "// 03b") + f'''
<g class="ln" style="animation-delay:.15s"><text x="{X}" y="96" class="dim"><tspan class="gr">$</tspan> render-city --concentric <tspan fill="#484f58"># newest day in the middle, one street per repo</tspan></text></g>
<g>{"".join(stars)}</g>
<circle cx="110" cy="170" r="40" fill="url(#moonglow)"/>
<circle cx="110" cy="170" r="14" fill="#e6edf3"/>
<circle cx="116" cy="165" r="12.5" fill="#03040a"/>
{info_svg}
{ground}
{roads}{road_edges}{centre_lines}
{plots}
{"".join(cars)}
{"".join(t[2] for t in items)}
<text x="{X}" y="{ly}" class="dim" style="font-size:11px">quiet</text>{legend}<text x="{X + 52 + 5*16 + 6}" y="{ly}" class="dim" style="font-size:11px">skyscraper</text>'''
    css = f"""@keyframes tw{{0%,100%{{opacity:.9}}50%{{opacity:.15}}}}
@keyframes lf{{0%,40%,100%{{opacity:1}}45%,60%{{opacity:.2}}}}
.s0{{animation:tw 3s infinite}}
.lf0{{animation:lf 5s infinite}}.lf1{{animation:lf 7s infinite 2s}}.lf2{{animation:lf 9s infinite 4s}}"""
    defs = ('<radialGradient id="moonglow"><stop offset="0" stop-color="#f0f6fc" stop-opacity=".22"/><stop offset="1" stop-color="#f0f6fc" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="lamp"><stop offset="0" stop-color="#ffd98a" stop-opacity=".55"/><stop offset="1" stop-color="#ffd98a" stop-opacity="0"/></radialGradient>'
            '<linearGradient id="beam" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#fff6d6" stop-opacity=".6"/><stop offset="1" stop-color="#fff6d6" stop-opacity="0"/></linearGradient>')
    desc = (f"Contribution city, concentric variation: an isometric night city with one building per day of the last year, "
            f"newest day in the middle, {total:,} contributions. {N} ring roads, one per repository contributed to"
            + (": " + ", ".join(named) if named else "") + ", each with a car driving it and street lamps along the road.")
    return slice_svg(h, body, title="Contribution city (concentric)", desc=desc,
                     text="~/contribution-city// 03b$ render-city --concentric # newest day in the middle, one street per repoquietskyscraper",
                     css=css, defs=defs, top=True, bottom=True)


def write(rel, svg):
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg)


def main():
    global OUT
    import argparse
    ap = argparse.ArgumentParser(description="Render the profile SVGs from data/*.json.")
    ap.add_argument("--theme", default=THEME, choices=list(THEMES), help="colour theme (see themes.py)")
    ap.add_argument("--data", type=pathlib.Path, default=DATA, help="folder with stats.json and articles.json")
    ap.add_argument("--out", type=pathlib.Path, default=OUT, help="folder to write the SVGs into")
    ap.add_argument("--variants", action="store_true", help="also render the experimental city variations (preview only)")
    args = ap.parse_args()
    OUT = args.out
    stats = json.load(open(args.data / "stats.json"))
    articles = json.load(open(args.data / "articles.json"))
    stars = stats.get("repo_stars", {})
    write("header.svg", build_header())
    for k, (key, *_) in enumerate(LINKS):
        write(f"links/{key}.svg", build_link_button(k))
    write("links/fill.svg", build_link_filler(len(LINKS)))
    write("stats.svg", build_stats(stats))
    if (args.data / "calendar.json").exists():
        write("contribution-city.svg", build_city(json.load(open(args.data / "calendar.json")), stats["updated"]))
    if args.variants and (args.data / "calendar.json").exists():
        repos = []
        for f in (args.data / "repos.json", ROOT / "_dev" / "repos.demo.json"):   # demo file: local dev fallback only
            if f.exists() and json.load(open(f)):
                repos = json.load(open(f))
                break
        write("contribution-city-concentric.svg",
              build_city_concentric(json.load(open(args.data / "calendar.json")), repos, stats["updated"]))
    write("projects.svg", build_projects_head())
    for i, p in enumerate(PROJECTS):
        write(f"card-{p['slug']}.svg", build_card(p, "L" if i % 2 == 0 else "R", 0.3 + i * 0.12, stars))
    write("stack.svg", build_stack())
    write("writing.svg", build_writing_head())
    for i, a in enumerate(articles[:5]):
        write(f"writing/post-{i+1}.svg", build_article_row(a, i))
    write("writing/all-articles.svg", build_writing_more())
    write("footer.svg", build_footer())
    print("rendered", len(list(OUT.rglob("*.svg"))), "SVGs into", OUT)


if __name__ == "__main__":
    main()
