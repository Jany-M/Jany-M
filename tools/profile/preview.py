"""Builds preview.html: the README as it will look on GitHub, plus colour switchers.
Local use only. Renders every theme from themes.py, so the presets are exact (city included);
the two pickers re-colour the currently selected preset on top.
Usage: python tools/profile/preview.py   (after fetch.py and readme.py)"""
import json, os, pathlib, re, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from themes import THEMES, DEFAULT

readme = (ROOT / "README.md").read_text()
rels = re.findall(r'src="\./([^"]+\.svg)"', readme)
sets = {}
for name in THEMES:
    out = pathlib.Path(tempfile.mkdtemp(prefix=f"prof-{name}-"))
    subprocess.run([sys.executable, str(HERE / "render.py"), "--theme", name, "--out", str(out)],
                   check=True, stdout=subprocess.DEVNULL)
    sets[name] = {r: (out / pathlib.Path(r).relative_to("assets")).read_text() for r in rels}
body = re.sub(r'src="\./([^"]+\.svg)"', lambda m: f'src="" data-svg="{m.group(1)}"', readme)
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
(ROOT / "preview.html").write_text(page)
print("preview.html written,", len(page) // 1024, "KB; themes:", ", ".join(THEMES))
