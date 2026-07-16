#!/usr/bin/env python3
"""Render a visual learning-journey page from the local learner model.

Replays every logged event chronologically (a faithful reconstruction of what a
live mentor would have tracked) and fills assets/journey-template.html. Output
is a single self-contained HTML file — no personal data ever enters the repo.

Usage: journey.py [output.html]   (default: $CL_HOME/journey.html)
"""

import datetime
import json
import os
import sys
from collections import defaultdict

CL_HOME = os.environ.get("CL_HOME") or os.path.expanduser("~/.continuous-learning")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "assets", "journey-template.html")

NUDGES = {"asked_basic_question": -0.3, "asked_advanced_question": 0.2,
          "used_correctly": 0.3, "struggled": -0.3, "was_taught": 0.1,
          "hands_on_completed": 0.5, "predicted_correctly": 0.4,
          "predicted_incorrectly": -0.3, "review_correct": 0.3,
          "review_partial": 0.1, "review_incorrect": -0.4}
LEARN = {"was_taught", "asked_basic_question", "struggled", "predicted_incorrectly"}
DO = {"used_correctly", "hands_on_completed", "asked_advanced_question", "predicted_correctly"}
LABEL = {"ai-llm": "AI & LLMs", "ci-cd": "CI/CD & Deploy", "security": "Security",
         "git": "Git", "databases": "Databases", "web-backend": "Web Backend",
         "web-frontend": "Web Frontend", "networking": "Networking", "python": "Python",
         "unix": "Unix/Linux", "macos": "macOS", "containers": "Containers",
         "cloud": "Cloud", "shell": "Shell", "javascript": "JavaScript",
         "kubernetes": "Kubernetes", "editors": "Editors", "other": "Product & Misc"}


def load(name, default):
    try:
        with open(os.path.join(CL_HOME, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def monday(iso):
    d = datetime.date.fromisoformat(iso[:10])
    return (d - datetime.timedelta(days=d.weekday())).isoformat()


def fmt_span(a, b):
    da, db = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    mon = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    left = f"{da.day} {mon[da.month - 1]}"
    right = f"{db.day} {mon[db.month - 1]} {db.year}"
    return f"{left} – {right}"


def wklabel(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[d.month - 1]} {d.day}"


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(CL_HOME, "journey.html")
    concepts = load("concepts.json", {})
    events = [e for e in
              (json.loads(l) for l in _lines("events.jsonl")) if e.get("concept")]
    if len(events) < 5:
        sys.exit("not enough learning events yet — use the plugin for a few sessions, "
                 "or run scripts/backfill.sh to seed from history")
    events.sort(key=lambda e: e.get("ts", ""))
    area_of = {k: v.get("area", "other") for k, v in concepts.items()}
    names = {k: v.get("name", k) for k, v in concepts.items()}

    weekly = defaultdict(lambda: {"learn": 0, "do": 0, "t": 0})
    for e in events:
        w = monday(e["ts"])
        weekly[w]["t"] += 1
        if e["type"] in LEARN:
            weekly[w]["learn"] += 1
        elif e["type"] in DO:
            weekly[w]["do"] += 1
    weeks = sorted(weekly)

    # chronological rating replay
    ratings = {}

    def apply(cid, t):
        c = ratings.setdefault(cid, {"rating": 2.0, "evidence": 0})
        if t not in NUDGES:
            return
        w = 2.0 if c["evidence"] == 0 else 1.0
        c["rating"] = max(0.2, min(5.0, c["rating"] + NUDGES[t] * w))
        c["evidence"] += 1

    traj = defaultdict(list)
    ei = 0
    for w in weeks:
        wend = (datetime.date.fromisoformat(w) + datetime.timedelta(days=7)).isoformat()
        while ei < len(events) and events[ei]["ts"][:10] < wend:
            apply(events[ei]["concept"], events[ei]["type"])
            ei += 1
        ba = defaultdict(lambda: [0.0, 0])
        for cid, c in ratings.items():
            a = area_of.get(cid, "other")
            ba[a][0] += c["rating"] * c["evidence"]
            ba[a][1] += c["evidence"]
        for a, (ws, ev) in ba.items():
            if ev:
                traj[a].append({"week": wklabel(w), "rating": round(ws / ev, 2)})

    area_final = defaultdict(lambda: [0.0, 0])
    for cid, c in ratings.items():
        a = area_of.get(cid, "other")
        area_final[a][0] += c["rating"] * c["evidence"]
        area_final[a][1] += c["evidence"]
    standing = sorted(([LABEL.get(a, a), round(ws / ev, 2), ev]
                       for a, (ws, ev) in area_final.items()), key=lambda x: -x[1])

    sig = sorted(([names.get(cid, cid).replace("-", " ").title() if names.get(cid, cid).islower()
                   else names.get(cid, cid), round(c["rating"], 2), c["evidence"]]
                  for cid, c in ratings.items() if c["evidence"] >= 3),
                 key=lambda x: -(x[1] * x[2]))[:8]

    # trajectory: emphasise two top risers + the biggest dipper, rest as context
    def rise(a):
        return traj[a][-1]["rating"] - traj[a][0]["rating"]
    with_ev = [a for a in traj if area_final[a][1] >= 4]
    risers = sorted(with_ev, key=lambda a: -rise(a))[:2]
    dipper = min(with_ev, key=rise) if with_ev else None
    ctx = [a for a in sorted(with_ev, key=lambda a: -area_final[a][1])
           if a not in risers and a != dipper][:3]
    series, cls_for = [], {}
    for i, a in enumerate(risers):
        cls_for[a] = "git" if i == 0 else "cicd"
    if dipper and dipper not in risers:
        cls_for[dipper] = "db"
    for a in risers + ([dipper] if dipper and dipper not in risers else []) + ctx:
        series.append({"name": LABEL.get(a, a).split(" &")[0].split("/")[0],
                       "cls": cls_for.get(a, "ctx"),
                       "emph": a in cls_for,
                       "pts": [p["rating"] for p in traj[a]]})

    metrics = load("metrics.json", {})

    def mcur(k):
        h = metrics.get(k, {}).get("history", [])
        return h[-1]["value"] if h else 0
    repos = sorted(((k.replace("github.stars.", "").split("/")[-1], v["history"][-1]["value"])
                    for k, v in metrics.items()
                    if k.startswith("github.stars.") and k != "github.stars.total"),
                   key=lambda x: -x[1])[:6]
    traction = sum(1 for k in metrics if k.startswith("github.stars.")
                   and k != "github.stars.total")
    goals = [[g["type"], g["text"]] for g in load("goals.json", [])
             if g.get("status") == "active"][:6]

    do_total = sum(1 for e in events if e["type"] in DO)
    learn_total = sum(1 for e in events if e["type"] in LEARN)
    graded = do_total + learn_total or 1
    fluency = round(100 * do_total / graded)
    lw = weekly[weeks[-1]]

    data = {
        "trajectory": {"weeks": [p["week"] for p in traj[series and risers[0] or list(traj)[0]]],
                       "series": series},
        "weekly": [{"w": wklabel(w), "learn": weekly[w]["learn"],
                    "do": weekly[w]["do"], "t": weekly[w]["t"]} for w in weeks],
        "standing": standing,
        "sig": sig,
        "repos": [[n, s] for n, s in repos],
        "goals": goals,
    }

    stars = mcur("github.stars.total")
    verdict_title = ('Yes — you’ve been <span class="em">learning</span>, '
                     'and here’s the trace to prove it.' if do_total >= learn_total
                     else 'You’re early — here’s the <span class="em">trace</span> '
                          'of what you’re building.')
    ratio = (f"nearly <b>{do_total / max(learn_total, 1):.1f}× as long demonstrating "
             "fluency as being taught.</b>" if do_total >= learn_total
             else "and the mentor is actively closing the gaps.")
    verdict_lede = (f"Real work, replayed event by event. Across <b>{len(set(e.get('session') for e in events))} sessions</b> "
                    f"the system logged <b>{len(events)} moments</b> of you learning or doing — "
                    f"and you spent {ratio}")

    tokens = {
        "EVENTS": len(events), "SESSIONS": _session_count(events),
        "CONCEPTS": len(area_final), "AREAS": len(area_final),
        "STARS": stars, "FORKS": mcur("github.forks.total"),
        "REPOS_TRACTION": traction, "DO": do_total, "LEARN": learn_total,
        "DO_PCT": fluency, "LEARN_PCT": 100 - fluency, "FLUENCY_PCT": fluency,
        "LW_DO": lw["do"], "LW_LEARN": lw["learn"],
        "SPAN": fmt_span(events[0]["ts"][:10], events[-1]["ts"][:10]),
        "VERDICT_TITLE": verdict_title, "VERDICT_LEDE": verdict_lede,
        "DATA": json.dumps(data, ensure_ascii=False),
    }

    html = open(TEMPLATE, encoding="utf-8").read()
    for k, v in tokens.items():
        html = html.replace(f"%%{k}%%", str(v))
    leftover = [t for t in ("%%",) if t in html and "%%DATA%%" not in html]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out_path} ({len(html)} bytes) — {len(events)} events, "
          f"{fluency}% fluency, {stars} stars")


def _lines(name):
    try:
        with open(os.path.join(CL_HOME, name), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield line
    except OSError:
        return


def _session_count(events):
    return len({e.get("session") for e in events if e.get("session")}) or len(events)


if __name__ == "__main__":
    main()
