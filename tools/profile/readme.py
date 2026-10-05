"""Updates the dynamic parts of README.md from data/*.json.

- the latest-articles block (Shambix blog) between <!-- writing:start --> and <!-- writing:end -->
  (links + alt text; the images themselves come from render.py)
- the alt text of the stats image, so screen readers get today's numbers

Everything else in the README is left exactly as it is.
"""
import datetime
import hashlib
import html
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
README = HERE.parent.parent / "README.md"
DATA = HERE / "data"


def writing_block(articles):
    lines = []
    for i, a in enumerate(articles[:5], 1):
        alt = html.escape(f'{a["title"]} — published {a["published_at"][:10]}, '
                          f'{a.get("category", "Blog")}', quote=True)
        lines.append(f'<a href="{html.escape(a["url"], quote=True)}"><img src="./assets/writing/post-{i}.svg" '
                     f'width="100%" align="top" alt="{alt}"></a>')
    return "<!-- writing:start -->\n" + "\n".join(lines) + "\n<!-- writing:end -->"


def days(n):
    return f"{n} day" if n == 1 else f"{n} days"


def stats_alt(d):
    since = datetime.date.fromisoformat(d["created_at"][:10])
    langs = sorted(d["languages"].items(), key=lambda kv: -kv[1])[:5]
    parts = [f'{d["stars"]} total stars',
             (f'{d["contributions_year"]} contributions in {d["year"]}, {d["contributions_all"]} all time'
              if "contributions_year" in d else f'{d["commits_year"]} commits in {d["year"]}, {d["commits_all"]} all time'),
             f'{d["prs"]} pull requests ({d["prs_merged"]} merged)',
             f'current streak {days(d["streak_current"])}, longest {days(d["streak_longest"])}',
             f'{d["followers"]} followers', f'{d["forks"]} forks',
             f'member since {since:%B %Y}']
    text = "Stats: " + "; ".join(parts) + ". Top languages: " + ", ".join(k for k, _ in langs) + "."
    return html.escape(text, quote=True)


def city_alt(calendar):
    total = sum(n for _, n in calendar)
    busiest = max(calendar, key=lambda t: t[1]) if calendar else None
    text = (f"Contribution city: an isometric night skyline with one building per day of the last year. "
            f"{total:,} contributions")
    if busiest and busiest[1]:
        d = datetime.date.fromisoformat(busiest[0])
        text += f", busiest day {d:%B} {d.day} with {busiest[1]}"
    return html.escape(text + ".", quote=True)


def main():
    stats = json.loads((DATA / "stats.json").read_text())
    articles = json.loads((DATA / "articles.json").read_text())
    s = README.read_text()

    s, n = re.subn(r"<!-- writing:start -->.*?<!-- writing:end -->", lambda _: writing_block(articles), s, flags=re.S)
    if n != 1:
        sys.exit("error: README needs exactly one <!-- writing:start --> … <!-- writing:end --> block")

    s, n = re.subn(r'(<img src="\./assets/stats\.svg[^"]*"[^>]*?alt=")[^"]*(")',
                   lambda m: m.group(1) + stats_alt(stats) + m.group(2), s)
    if n != 1:
        sys.exit("error: README needs exactly one stats.svg image with an alt attribute")

    cal_file = DATA / "calendar.json"
    if cal_file.exists():   # optional section: only touched when the README has the city image
        s = re.sub(r'(<img src="\./assets/contribution-city\.svg[^"]*"[^>]*?alt=")[^"]*(")',
                   lambda mm: mm.group(1) + city_alt(json.loads(cal_file.read_text())) + mm.group(2), s)

    # cache-bust: GitHub's image proxy caches SVGs by URL, so tag each one with a hash of its content
    def bust(m):
        h = hashlib.md5((HERE.parent.parent / m.group(1)).read_bytes()).hexdigest()[:8]
        return f'src="./{m.group(1)}?v={h}"'
    s = re.sub(r'src="\./(assets/[^"?]+\.svg)(?:\?v=\w+)?"', bust, s)

    README.write_text(s)
    print("README updated")


if __name__ == "__main__":
    main()
