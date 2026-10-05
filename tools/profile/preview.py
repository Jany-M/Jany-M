"""Local preview, completely separate from the repo.

Everything is generated inside  _dev/preview/  (git-ignored): data, SVGs, a copy of README.md and
preview.html. Nothing under tools/profile/data, assets/ or README.md is ever touched, so there is
nothing to discard or accidentally commit.

    python tools/profile/preview.py              refresh data (GitHub + blog), render, build preview.html
    python tools/profile/preview.py --no-fetch   reuse the data already in _dev/preview/data

Set PROFILE_TOKEN in your shell first to include private repos/contributions (not saved anywhere).
Then open _dev/preview/preview.html. It shows the README as GitHub will, colour switchers, and the
experimental city variations below it.
"""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
SAND = REPO / "_dev" / "preview"
sys.path.insert(0, str(HERE))
from themes import THEMES, DEFAULT

# experimental city variations, shown below the real README (not part of it): (file, label)
VARIANTS = [("assets/contribution-city-alt.svg", "Alternative city model (the one NOT selected by CITY_MODEL in render.py)")]

def _write(path, text):
    """UTF-8 + LF on every OS (Windows would otherwise write cp1252 / CRLF and dirty the repo)."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ── sandbox: copy of the README template, data seeded from the repo only the first time
(SAND / "data").mkdir(parents=True, exist_ok=True)
(SAND / "assets").mkdir(parents=True, exist_ok=True)
_write(SAND / "README.md", (REPO / "README.md").read_text(encoding="utf-8").replace("\r\n", "\n"))        # fresh template every run
for f in (HERE / "data").glob("*.json"):
    if not (SAND / "data" / f.name).exists():
        shutil.copyfile(f, SAND / "data" / f.name)
env = dict(os.environ, PROFILE_ROOT=str(SAND))

def run(script, *args, **kw):
    subprocess.run([sys.executable, str(HERE / script), *args], check=True, env=env, **kw)

if "--no-fetch" not in sys.argv:
    run("fetch.py")
run("render.py", "--variants")          # default theme -> _dev/preview/assets
run("readme.py")                        # updates _dev/preview/README.md only

readme = (SAND / "README.md").read_text(encoding="utf-8")
rels = re.findall(r'src="\./([^"?]+\.svg)(?:\?v=\w+)?"', readme) + [v[0] for v in VARIANTS]
sets = {}
for name in THEMES:
    out = pathlib.Path(tempfile.mkdtemp(prefix=f"prof-{name}-"))
    run("render.py", "--theme", name, "--out", str(out), "--variants", stdout=subprocess.DEVNULL)
    sets[name] = {r: (out / pathlib.Path(r).relative_to("assets")).read_text(encoding="utf-8") for r in rels}
body = re.sub(r'src="\./([^"?]+\.svg)(?:\?v=\w+)?"', lambda m: f'src="" data-svg="{m.group(1)}"', readme)
extra = "".join(f'<h3 style="max-width:880px;margin:32px auto 8px;font:600 14px system-ui">{label}</h3>'
                f'<div style="max-width:880px;margin:0 auto 24px"><img data-svg="{rel}" width="100%" alt=""></div>'
                for rel, label in VARIANTS)
page = """<!doctype html><meta charset="utf-8"><title>Jany-M profile preview</title>
<style>
body{background:#0d1117;margin:0;font-family:system-ui,sans-serif;color:#c9d1d9}
#bar{position:sticky;top:0;z-index:9;background:#161b22;border-bottom:1px solid #30363d;padding:10px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;font-size:14px}
#bar input[type=color]{width:42px;height:28px;border:0;background:none;padding:0;cursor:pointer;vertical-align:middle}
.sw{width:22px;height:22px;border-radius:50%;border:2px solid #30363d;cursor:pointer;display:inline-block;vertical-align:middle;margin-left:4px}
.sw.on{border-color:#fff}
button{background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:4px 10px;cursor:pointer}
#wrap{max-width:880px;margin:24px auto;border:1px solid #30363d;border-radius:6px;padding:16px}
</style>
<div id="bar">
 <label>Main <input type="color" id="main"></label>
 <label>Accent <input type="color" id="acc"></label>
 <span id="presets"></span>
 <button id="reset">Reset</button>
 <span style="opacity:.6">preview only: nothing here changes the real files</span>
</div>
<div id="wrap">""" + body + """</div>
""" + extra + """
<script>
const SETS = """ + json.dumps(sets) + """, THEMES = """ + json.dumps(THEMES) + """, DEFAULT = """ + json.dumps(DEFAULT) + """;
let cur = DEFAULT;
const mainI = document.getElementById("main"), accI = document.getElementById("acc");
function apply() {
  const [bm, ba] = THEMES[cur];
  document.querySelectorAll("img[data-svg]").forEach(img => {
    const t = SETS[cur][img.dataset.svg].split(bm).join(mainI.value).split(ba).join(accI.value);
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(t);
  });
}
function pick(name) {
  cur = name; [mainI.value, accI.value] = THEMES[name];
  document.querySelectorAll(".sw").forEach(s => s.classList.toggle("on", s.dataset.t === name));
  apply();
}
Object.entries(THEMES).forEach(([name, [m, a]]) => {
  const s = document.createElement("span"); s.className = "sw"; s.dataset.t = name; s.title = name;
  s.style.background = `linear-gradient(135deg,${m} 50%,${a} 50%)`;
  s.onclick = () => pick(name);
  document.getElementById("presets").appendChild(s);
});
mainI.oninput = accI.oninput = apply;
document.getElementById("reset").onclick = () => pick(DEFAULT);
pick(DEFAULT);
</script>"""
_write(SAND / "preview.html", page)
print("preview written to", SAND / "preview.html", f"({len(page) // 1024} KB)")
