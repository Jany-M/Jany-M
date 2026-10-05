"""Fetches fresh profile data into data/stats.json, data/articles.json and data/calendar.json
(last 53 weeks of daily contributions).

Sources:
  GitHub  -> stats, languages, contribution calendar (GraphQL when a token is available)
  Shambix -> latest blog posts from the public WordPress REST API (no key needed)

Environment variables (all optional):
  PROFILE_TOKEN  classic personal access token (read:user, optionally repo). Lets contribution,
                 PR and streak numbers include private work. Falls back to GITHUB_TOKEN.
  GITHUB_TOKEN   the token GitHub Actions provides automatically (public data only).

With no token at all (local preview) the GitHub part falls back to public REST + the public
contributions graph. Each source is fetched independently; if one fails its previous values
are kept, so a flaky API never blanks out part of the profile.
"""
import datetime
import html
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

USER = "Jany-M"
BLOG_API = "https://www.shambix.com/wp-json/wp/v2"
DATA = pathlib.Path(__file__).resolve().parent / "data"
UA = "Jany-M-profile-updater"


# ─────────────────────────────── helpers ───────────────────────────────
def http(url, *, headers=None, body=None, timeout=30):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={"User-Agent": UA, **(headers or {})})
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def http_json(url, **kw):
    kw.setdefault("headers", {})["Accept"] = "application/json"
    return json.loads(http(url, **kw))


def graphql(token, query, variables=None):
    res = http_json("https://api.github.com/graphql", headers={"Authorization": f"bearer {token}"},
                    body={"query": query, "variables": variables or {}})
    if res.get("errors"):
        raise RuntimeError("GraphQL error: " + "; ".join(e.get("message", "?") for e in res["errors"]))
    return res["data"]


def load(name, default):
    try:
        return json.loads((DATA / name).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def warn(msg):
    print(f"::warning::{msg}" if os.environ.get("GITHUB_ACTIONS") else f"warning: {msg}", file=sys.stderr)


# ─────────────────────────────── GitHub ────────────────────────────────
PROFILE_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    pullRequests { totalCount }
    merged: pullRequests(states: MERGED) { totalCount }
    contributionsCollection { contributionYears }
    owned: repositories(ownerAffiliations: OWNER) { totalCount }
    own: repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      nodes {
        name
        isPrivate
        stargazerCount
        forkCount
        languages(first: 20) { edges { size node { name } } }
      }
    }
    other: repositories(ownerAffiliations: [COLLABORATOR, ORGANIZATION_MEMBER], isFork: false, first: 100) {
      nodes {
        name
        isPrivate
        languages(first: 20) { edges { size node { name } } }
      }
    }
  }
}"""


def years_query(years):
    parts = []
    for y in years:
        parts.append(f"""
    y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") {{
      totalCommitContributions
      contributionCalendar {{ totalContributions weeks {{ contributionDays {{ date contributionCount }} }} }}
    }}""")
    return "query($login: String!) {\n  user(login: $login) {" + "".join(parts) + "\n  }\n}"


def streaks(days, today):
    """days: {date: count}. Current streak may end yesterday if today has no contributions yet."""
    dates = sorted(d for d in days if d <= today)
    longest = run = 0
    for d in dates:
        run = run + 1 if days[d] > 0 else 0
        longest = max(longest, run)
    current, d = 0, today
    if days.get(d, 0) == 0:
        d -= datetime.timedelta(days=1)
    while days.get(d, 0) > 0:
        current += 1
        d -= datetime.timedelta(days=1)
    return current, longest


# markup / config languages that would otherwise show up as "languages"
IGNORE_LANGS = {"CSS", "SCSS", "Less", "HTML", "ApacheConf", "Batchfile", "VBScript", "Dockerfile", "Makefile", "Smarty", "Shell"}


def assemble(today, *, created_at, followers, prs, prs_merged, repos, days, commits_all, repo_total=None):
    """Shared by the GraphQL path and the public fallback. repos: [{name, stars, forks, langs{}}]."""
    current, longest = streaks(days, today)
    # last 53 weeks, starting on a Sunday like GitHub's own graph (feeds the contribution city)
    start = today - datetime.timedelta(weeks=52)
    start -= datetime.timedelta(days=(start.weekday() + 1) % 7)
    calendar = [[d.isoformat(), days.get(d, 0)] for d in
                (start + datetime.timedelta(days=i) for i in range((today - start).days + 1))]
    # Languages: each repo/language pair counts sqrt(bytes), so a few huge bundled libraries
    # (typical for WordPress plugins) can't drown out everything else.
    langs = {}
    for r in repos:
        for k, v in r["langs"].items():
            if k not in IGNORE_LANGS:
                langs[k] = langs.get(k, 0) + v ** 0.5
    return {
        "created_at": created_at,
        "followers": followers,
        "prs": prs,
        "prs_merged": prs_merged,
        "stars": sum(r["stars"] for r in repos),
        "forks": sum(r["forks"] for r in repos),
        # every repo you own (public + private, forks included); stars/languages below skip forks
        "repo_count": repo_total if repo_total is not None else sum(1 for r in repos if r["own"]),
        # public repo names only: this file is committed to a public repo
        "repo_stars": {r["name"]: r["stars"] for r in repos if r["own"] and not r["private"]},
        "languages": {k: round(v) for k, v in sorted(langs.items(), key=lambda kv: -kv[1])},
        "year": today.year,
        "contributions_year": sum(n for d, n in days.items() if d.year == today.year),
        "contributions_all": sum(days.values()),
        "commits_all": commits_all,
        "streak_current": current,
        "streak_longest": longest,
        "_calendar": calendar,
    }


def fetch_github(token, today):
    u = graphql(token, PROFILE_QUERY, {"login": USER})["user"]
    years = sorted(u["contributionsCollection"]["contributionYears"])
    ydata = graphql(token, years_query(years), {"login": USER})["user"] if years else {}
    days, commits_all = {}, 0
    for y in years:
        c = ydata[f"y{y}"]
        commits_all += c["totalCommitContributions"]
        for w in c["contributionCalendar"]["weeks"]:
            for day in w["contributionDays"]:
                days[datetime.date.fromisoformat(day["date"])] = day["contributionCount"]
    repos = [{"name": r["name"], "own": own, "private": r["isPrivate"],
              "stars": r.get("stargazerCount", 0) if own else 0, "forks": r.get("forkCount", 0) if own else 0,
              "langs": {e["node"]["name"]: e["size"] for e in r["languages"]["edges"]}}
             for own, key in ((True, "own"), (False, "other")) for r in u[key]["nodes"]]
    return assemble(today, created_at=u["createdAt"], followers=u["followers"]["totalCount"],
                    prs=u["pullRequests"]["totalCount"], prs_merged=u["merged"]["totalCount"],
                    repos=repos, days=days, commits_all=commits_all, repo_total=u["owned"]["totalCount"])


def fetch_github_public(today):
    """No token: public REST API + the public contributions graph. Good enough for a local preview.
    The graph includes private work only if 'Private contributions' is enabled in your GitHub profile settings."""
    u = http_json(f"https://api.github.com/users/{USER}")
    raw = http_json(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
    repos = []
    for r in raw:
        if r["fork"]:
            continue
        try:
            langs = http_json(r["languages_url"])
        except Exception:  # noqa: BLE001
            langs = {}
        repos.append({"name": r["name"], "own": True, "private": False, "stars": r["stargazers_count"],
                      "forks": r["forks_count"], "langs": langs})
    count = lambda q: http_json("https://api.github.com/search/issues?q=" + urllib.parse.quote(q) + "&per_page=1")["total_count"]
    prs, merged = count(f"author:{USER} type:pr"), count(f"author:{USER} type:pr is:merged")
    days = {}
    for y in range(int(u["created_at"][:4]), today.year + 1):
        page = http(f"https://github.com/users/{USER}/contributions?from={y}-01-01&to={y}-12-31")
        cells = {m.group(2): m.group(1) for m in re.finditer(r'<td[^>]*data-date="([\d-]+)"[^>]*id="([^"]+)"', page)}
        for m in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>\s*(No|\d+) contributions?', page):
            if m.group(1) in cells:
                days[datetime.date.fromisoformat(cells[m.group(1)])] = 0 if m.group(2) == "No" else int(m.group(2))
    return assemble(today, created_at=u["created_at"], followers=u["followers"], prs=prs, prs_merged=merged,
                    repos=repos, days=days, commits_all=0)


# ───────────────────── repos contributed to (last 365 days) ─────────────────────
REPOS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      commits: commitContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner isPrivate } contributions { totalCount } }
      prs: pullRequestContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner isPrivate } contributions { totalCount } }
      issues: issueContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner isPrivate } contributions { totalCount } }
      reviews: pullRequestReviewContributionsByRepository(maxRepositories: 100) { repository { nameWithOwner isPrivate } contributions { totalCount } }
    }
  }
}"""


def fetch_repos(token, today):
    """[{name, private, count}] for every repo contributed to in the last year. Private repo names are
    never stored (this file is committed to a public repo): they appear as name=None."""
    frm = (today - datetime.timedelta(days=364)).isoformat() + "T00:00:00Z"
    to = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cc = graphql(token, REPOS_QUERY, {"login": USER, "from": frm, "to": to})["user"]["contributionsCollection"]
    merged = {}
    for key in ("commits", "prs", "issues", "reviews"):
        for e in cc[key]:
            r = e["repository"]
            m = merged.setdefault(r["nameWithOwner"], {"name": None if r["isPrivate"] else r["nameWithOwner"],
                                                       "private": r["isPrivate"], "count": 0})
            m["count"] += e["contributions"]["totalCount"]
    return sorted(merged.values(), key=lambda r: -r["count"])


def fetch_repos_public():
    """No token: repos from your public events (GitHub only keeps the last ~90 days)."""
    counts = {}
    for page in (1, 2, 3):
        try:
            evs = http_json(f"https://api.github.com/users/{USER}/events/public?per_page=100&page={page}")
        except Exception:  # noqa: BLE001
            break
        for ev in evs:
            counts[ev["repo"]["name"]] = counts.get(ev["repo"]["name"], 0) + 1
    return sorted(({"name": k, "private": False, "count": v} for k, v in counts.items()), key=lambda r: -r["count"])


# ─────────────────────────────── Shambix blog ──────────────────────────
def fetch_blog(limit=5):
    cats = {c["id"]: html.unescape(c["name"]) for c in
            http_json(f"{BLOG_API}/categories?per_page=100&_fields=id,name")}
    posts = http_json(f"{BLOG_API}/posts?per_page={limit}&_fields=id,date,link,title,categories")
    out = []
    for p in posts:
        names = [cats[c] for c in p["categories"] if c in cats and cats[c] not in ("Uncategorized", "News")]
        out.append({"published_at": p["date"], "title": html.unescape(p["title"]["rendered"]),
                    "url": p["link"], "category": (names or ["Blog"])[0]})
    return out


# ──────────────────────────────── main ─────────────────────────────────
def main():
    today = datetime.datetime.now(datetime.timezone.utc).date()
    stats = load("stats.json", {})
    articles = load("articles.json", [])
    ok = False

    token = os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN")
    try:
        gh = fetch_github(token, today) if token else fetch_github_public(today)
        save("calendar.json", gh.pop("_calendar"))
        stats.update(gh)
        ok = True
        print("github: ok " + ("(with private contributions)" if os.environ.get("PROFILE_TOKEN")
                               else "(public token)" if token else "(public preview, no token)"))
    except Exception as ex:  # noqa: BLE001
        warn(f"GitHub fetch failed, keeping previous stats: {ex}")

    try:
        save("repos.json", fetch_repos(token, today) if token else fetch_repos_public())
        print("repos: ok")
    except Exception as ex:  # noqa: BLE001
        warn(f"Repo list unavailable, keeping previous: {ex}")

    try:
        latest = fetch_blog()
        if latest:
            articles = latest
        ok = True
        print(f"blog: ok ({len(latest)} posts)")
    except Exception as ex:  # noqa: BLE001
        warn(f"Blog fetch failed, keeping previous values: {ex}")

    if not ok:
        print("error: every source failed, nothing updated", file=sys.stderr)
        sys.exit(1)
    stats["updated"] = today.isoformat()
    save("stats.json", stats)
    save("articles.json", articles)


if __name__ == "__main__":
    main()
