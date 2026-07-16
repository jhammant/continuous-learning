#!/usr/bin/env python3
"""Continuous Learning — local data layer for the continuous-learning plugin.

One JSON-backed learner model per user: per-concept ratings (0-5), an
append-only log of learning events, and spaced-repetition recall cards.
Everything lives under ~/.continuous-learning (override with CL_HOME).
Stdlib only; every subcommand is safe to run repeatedly.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys

CL_HOME = os.environ.get("CL_HOME") or os.path.expanduser("~/.continuous-learning")
SCRIPT = os.path.abspath(__file__)

MODES = ("off", "quiet", "active", "coach")

# How much one piece of evidence moves a concept rating (0-5 scale).
# First-ever evidence for a concept is weighted double.
NUDGES = {
    "asked_basic_question": -0.3,
    "asked_advanced_question": 0.2,
    "used_correctly": 0.3,
    "struggled": -0.3,
    "was_taught": 0.1,
    "hands_on_completed": 0.5,
    "predicted_correctly": 0.4,
    "predicted_incorrectly": -0.3,
    "check_ignored": 0.0,
    "review_correct": 0.3,
    "review_partial": 0.1,
    "review_incorrect": -0.4,
    "self_study": 0.2,  # you studied it yourself (e.g. read the docs), not AI-taught
}

AREAS = (
    "git", "shell", "unix", "networking", "containers", "kubernetes",
    "ci-cd", "cloud", "security", "databases", "web-backend",
    "web-frontend", "python", "javascript", "ai-llm", "macos",
    "editors", "other",
)


# ---------------------------------------------------------------- storage

def path(name):
    return os.path.join(CL_HOME, name)


def ensure_home():
    os.makedirs(os.path.join(CL_HOME, "logs"), exist_ok=True)


def load(name, default):
    try:
        with open(path(name), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return default
    # a corrupt-but-parseable file (e.g. a list where a dict belongs) must not
    # crash callers that iterate .items()
    return data if isinstance(data, type(default)) else default


def save(name, data):
    ensure_home()
    # pid-unique tmp path: hooks, extraction, and live log-event can overlap
    tmp = f"{path(name)}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path(name))


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def today():
    return dt.date.today()


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def append_event_log(records):
    ensure_home()
    with open(path("events.jsonl"), "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def read_event_log():
    try:
        with open(path("events.jsonl"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


# ---------------------------------------------------------------- model

def norm_concept(cid):
    cid = re.sub(r"[^a-z0-9]+", "-", cid.strip().lower()).strip("-")
    return cid or "unknown"


def apply_event(concepts, ev, ts=None):
    """Apply one learning event to the concept model. Returns concept id.

    ts (ISO 8601) backdates the evidence, e.g. when backfilling old sessions;
    it never regresses a concept's last_seen.
    """
    etype = ev.get("type")
    if not isinstance(etype, str) or etype not in NUDGES:
        return None
    if not isinstance(ev.get("concept"), str):
        return None
    cid = norm_concept(ev["concept"])
    if cid == "unknown":
        return None
    c = concepts.get(cid)
    if c is None:
        c = {
            "name": str(ev.get("name") or cid.replace("-", " ")),
            "area": ev.get("area") if ev.get("area") in AREAS else "other",
            "rating": 2.0,
            "evidence": 0,
        }
        concepts[cid] = c
    weight = 2.0 if c["evidence"] == 0 else 1.0
    c["rating"] = round(clamp(c["rating"] + NUDGES[etype] * weight, 0.2, 5.0), 2)
    c["evidence"] += 1
    seen = ts or now_iso()
    if seen > c.get("last_seen", ""):
        c["last_seen"] = seen
    if ev.get("area") in AREAS and c.get("area", "other") == "other":
        c["area"] = ev["area"]
    return cid


def apply_decay(concepts):
    """Knowledge fades: after 60 idle days, drift ratings down 0.15/month."""
    changed = False
    for c in concepts.values():
        seen = c.get("last_seen")
        if not seen or c["rating"] <= 1.0:
            continue
        try:
            idle = (today() - dt.datetime.fromisoformat(seen).date()).days
        except ValueError:
            continue
        if idle <= 60:
            continue
        last = c.get("last_decay")
        if last and (today() - dt.date.fromisoformat(last)).days < 30:
            continue
        c["rating"] = round(max(1.0, c["rating"] - 0.15), 2)
        c["last_decay"] = today().isoformat()
        changed = True
    return changed


def add_review_card(reviews, concept, question, hint="", source=""):
    concept = norm_concept(concept)  # hash the normalized id or dedupe misses
    rid = hashlib.sha1((concept + "|" + question).encode()).hexdigest()[:8]
    if any(r["id"] == rid for r in reviews):
        return None
    reviews.append({
        "id": rid,
        "concept": concept,
        "question": question,
        "hint": hint or "",
        "source": source or "",
        "created": today().isoformat(),
        "due": (today() + dt.timedelta(days=2)).isoformat(),
        "interval": 2,
        "reps": 0,
    })
    return rid


# ---------------------------------------------------------------- context

UNCALIBRATED = """<continuous-learning-mentor>
Continuous Learning is installed but not calibrated yet, so its mentor layer is dormant.
If a natural pause occurs (a task just finished), mention ONCE, in one sentence, that
running /continuous-learning:profile (~1 minute) will calibrate it. Do not mention it
again this session. Otherwise behave normally.
</continuous-learning-mentor>"""

CHECK_RULE_ACTIVE = """2. Up to 2 optional micro-checks per session, ONLY at the end of a turn where the task
   is done. One short paragraph, clearly marked "**Optional check:**", tied to a
   developing concept that just came up. Prefer prediction over recall ("what will X do?"
   beats "what is X?"). If a check is ignored, log check_ignored and offer no more this
   session."""

CHECK_RULE_COACH = CHECK_RULE_ACTIVE + """
   Coach mode: when a small, safe, self-contained piece of a task fits a developing
   concept, offer to leave it to the user with a hint instead of doing it yourself.
   Never for destructive or blocking steps; if they decline or ignore, just do it."""

CHECK_RULE_QUIET = """2. No checks and no unsolicited teaching asides — observe and log only. Still answer
   teaching questions when asked directly."""


def cmd_hook_session_start(args):
    if os.environ.get("CL_EXTRACT"):
        return
    # drain stdin so the hook pipe closes cleanly
    try:
        sys.stdin.read()
    except OSError:
        pass
    settings = load("settings.json", {})
    mode = settings.get("mode", "active")
    if mode == "off":
        return
    ensure_home()
    if not settings.get("calibrated"):
        print(UNCALIBRATED)
        return

    concepts = load("concepts.json", {})
    if apply_decay(concepts):
        save("concepts.json", concepts)

    weak = sorted(
        (kv for kv in concepts.items() if kv[1]["rating"] < 3.0),
        key=lambda kv: kv[1].get("last_seen", ""), reverse=True,
    )[:6]
    strong = sorted(
        (kv for kv in concepts.items() if kv[1]["rating"] >= 4.0),
        key=lambda kv: kv[1]["rating"], reverse=True,
    )[:5]
    due = [r for r in load("reviews.json", []) if r["due"] <= today().isoformat()]

    def fmt(items):
        return ", ".join(f"{cid} {c['rating']:.1f} ({c.get('area', 'other')})"
                         for cid, c in items) or "none yet"

    check_rule = {"active": CHECK_RULE_ACTIVE, "coach": CHECK_RULE_COACH,
                  "quiet": CHECK_RULE_QUIET}[mode]
    due_note = (f"{len(due)} — at a natural pause, mention that "
                "`/continuous-learning:recall` takes ~2 minutes." if due else "0")

    metrics = load("metrics.json", {})
    stars = metric_current(metrics, "github.stars.total")
    if stars is not None:
        _, star_delta = metric_delta(metrics, "github.stars.total",
                                     (dt.datetime.now(dt.timezone.utc)
                                      - dt.timedelta(days=14)).isoformat(timespec="seconds"))
        d = f" ({star_delta:+g} /14d)" if star_delta else ""
        metrics_line = f"\n- Outcome metric — GitHub stars: {stars}{d}"
    else:
        metrics_line = ""

    paths = [p for p in load("paths.json", []) if p.get("status") == "active"]
    path_block = ""
    if paths:
        rows = []
        for p in paths[:3]:
            pr = path_progress(p, concepts)
            nxt = pr["next"]
            step = (f" — next step: {nxt} (aim {next((s['target'] for s in pr['steps'] if s['concept']==nxt), '')})"
                    if nxt else " — all steps met 🎉")
            rows.append(f"  - {pr['title']}: {pr['met']}/{pr['total']} steps{step}")
        path_block = (
            "\nActive learning paths (curricula the user is walking — when work touches the\n"
            "next step, lean in and offer to go deeper on it):\n" + "\n".join(rows) + "\n")

    active_goals = [g for g in load("goals.json", []) if g.get("status") == "active"]
    if active_goals:
        lines = "\n".join(f"  - {g['text']} [{g['type']}]" for g in active_goals[:6])
        goals_block = (
            "\nActive goals (the user set these to steer their direction):\n" + lines +
            "\nWhen the current task clearly advances a goal, say so in one line. When the\n"
            "user seems to be working far from every stated goal, note it once, gently —\n"
            "they explicitly asked to be told when they drift. Never block or redirect work\n"
            "over a goal; surface, don't steer.\n")
    else:
        goals_block = ""

    print(f"""<continuous-learning-mentor>
Mentor layer: ON (mode: {mode}). You are both assistant and mentor: help first, teach
through the work, never block or slow it.

Learner model (ratings 0-5; files under {CL_HOME}/):
- Developing concepts (teach toward these when they come up): {fmt(weak)}
- Strong concepts (skip basic explanations): {fmt(strong)}
- Recall cards due: {due_note}{metrics_line}
{path_block}{goals_block}
Session rules:
1. When work touches a developing concept, add ONE extra sentence of why/how at the
   user's level, inline as you work. Don't explain strong concepts.
{check_rule}
3. Log evidence about the USER as you notice it (their questions, fluent usage,
   struggles, hands-on wins) — max ~5 logs/session:
   python3 "{SCRIPT}" log-event --concept <kebab-id> --area <area> --type <type> --note "<one line>"
   Types: asked_basic_question, asked_advanced_question, used_correctly, struggled,
   was_taught, hands_on_completed, predicted_correctly, predicted_incorrectly,
   check_ignored, self_study (user studied it themselves, e.g. read the docs).
   Areas: {", ".join(AREAS)}.
4. A moment worth revisiting in a few days? Add a recall card (max 2/session):
   python3 "{SCRIPT}" add-review --concept <kebab-id> --question "..." --hint "..."
5. Urgency, frustration, or "just do it" → suspend all teaching for the session
   (keep logging silently).
6. For detailed pedagogy guidance, load the continuous-learning:mentor-playbook skill.
</continuous-learning-mentor>""")


# ---------------------------------------------------------------- hooks/queue

def read_queue_sids(name):
    sids = set()
    try:
        with open(path(name), encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    sids.add(line.split("\t")[0])
    except OSError:
        pass
    return sids


def cmd_hook_stop(args):
    if os.environ.get("CL_EXTRACT"):
        return
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    # off means off: sessions run while disabled are never even queued
    if load("settings.json", {}).get("mode", "active") == "off":
        return
    sid = data.get("session_id")
    tpath = data.get("transcript_path")
    if not sid or not tpath:
        return
    if sid in read_queue_sids("queue.txt") | read_queue_sids("queue.done.txt"):
        return
    ensure_home()
    with open(path("queue.txt"), "a", encoding="utf-8") as f:
        f.write(f"{sid}\t{tpath}\n")


def cmd_queue_pending(args):
    done = read_queue_sids("queue.done.txt")
    seen = set()
    try:
        with open(path("queue.txt"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                sid = line.split("\t")[0]
                if sid not in done and sid not in seen:
                    seen.add(sid)
                    print(line)
    except OSError:
        pass


def cmd_queue_done(args):
    ensure_home()
    with open(path("queue.done.txt"), "a", encoding="utf-8") as f:
        f.write(f"{args.session_id}\t{today().isoformat()}\n")


def cmd_queue_add(args):
    """Enqueue one transcript; exit 1 if already queued or done."""
    if args.session_id in (read_queue_sids("queue.txt")
                           | read_queue_sids("queue.done.txt")):
        print("skipped (already queued or done)")
        sys.exit(1)
    ensure_home()
    with open(path("queue.txt"), "a", encoding="utf-8") as f:
        f.write(f"{args.session_id}\t{args.transcript_path}\n")
    print("queued")


def cmd_attempt(args):
    """Increment and print the extraction attempt count for a session."""
    ensure_home()
    counts = {}
    try:
        with open(path("queue.attempts"), encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) == 2 and parts[1].isdigit():
                    counts[parts[0]] = int(parts[1])
    except OSError:
        pass
    counts[args.session_id] = counts.get(args.session_id, 0) + 1
    tmp = f"{path('queue.attempts')}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        for sid, n in counts.items():
            f.write(f"{sid} {n}\n")
    os.replace(tmp, path("queue.attempts"))
    print(counts[args.session_id])


# ---------------------------------------------------------------- transcript

SYS_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def block_text(block):
    btype = block.get("type")
    if btype == "text":
        return block.get("text", "")
    if btype == "tool_use":
        name = block.get("name", "")
        inp = block.get("input") or {}
        if name == "Bash":
            return f"[ran: {(inp.get('command') or '')[:160]}]"
        if name in ("Edit", "Write") and inp.get("file_path"):
            return f"[{name.lower()}d file: {inp['file_path']}]"
        return ""
    return ""


def cmd_digest_transcript(args):
    """Reduce a session transcript (JSONL) to a compact USER/ASSISTANT digest.

    Prints nothing if the session is too small to carry learning signal.
    """
    parts = []
    try:
        f = open(args.transcript, encoding="utf-8")
    except OSError:
        sys.exit(3)  # unreadable is not the same as empty: caller should retry
    with f:
        for line in f:
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("isMeta"):
                continue
            role = obj.get("type")
            if role not in ("user", "assistant"):
                continue
            content = (obj.get("message") or {}).get("content")
            if isinstance(content, str):
                texts = [content]
            elif isinstance(content, list):
                if any(isinstance(b, dict) and b.get("type") == "tool_result"
                       for b in content):
                    continue  # tool output echoed back, not the human speaking
                texts = [block_text(b) for b in content if isinstance(b, dict)]
            else:
                continue
            text = SYS_RE.sub("", "\n".join(t for t in texts if t)).strip()
            if not text:
                continue
            parts.append(f"{role.upper()}: {text[:1200]}")

    digest = "\n\n".join(parts)
    if len(digest) < 400:
        return
    if len(digest) > 24000:
        digest = digest[:8000] + "\n\n[... middle truncated ...]\n\n" + digest[-15000:]
    print(digest)


# ---------------------------------------------------------------- events in

def parse_llm_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in input")
    return json.loads(text[start:end + 1])


def cmd_apply_events(args):
    """Read {"events": [...], "recall": [...]} JSON from stdin and merge it."""
    if args.ts:
        try:
            dt.datetime.fromisoformat(args.ts)
        except ValueError:
            sys.exit(f"invalid --ts: {args.ts}")
    data = parse_llm_json(sys.stdin.read())
    events = data.get("events") or []
    recall = data.get("recall") or []

    concepts = load("concepts.json", {})
    reviews = load("reviews.json", [])
    logged, ts = [], args.ts or now_iso()

    for ev in events[:12]:
        if not isinstance(ev, dict):
            continue
        try:
            cid = apply_event(concepts, ev, ts=args.ts)
        except (TypeError, ValueError, AttributeError):
            continue  # one malformed event must not sink the whole session
        if cid:
            logged.append({"ts": ts, "session": args.session, "concept": cid,
                           "type": ev["type"], "note": str(ev.get("note") or "")[:200]})

    # Recall cards reference "what you did recently" — stale ones from a deep
    # backfill would be confusing, so only mint cards for recent sessions.
    recall_cutoff = (dt.datetime.now(dt.timezone.utc)
                     - dt.timedelta(days=14)).isoformat(timespec="seconds")
    skip_recall = bool(args.ts) and args.ts < recall_cutoff

    added = 0
    if not skip_recall:
        for r in recall[:3]:
            if not (isinstance(r, dict) and isinstance(r.get("concept"), str)
                    and isinstance(r.get("question"), str)):
                continue
            if add_review_card(reviews, r["concept"], r["question"],
                               str(r.get("hint") or ""), args.session):
                added += 1

    save("concepts.json", concepts)
    save("reviews.json", reviews)
    append_event_log(logged)
    print(f"applied {len(logged)} events, added {added} recall cards")


def cmd_log_event(args):
    concepts = load("concepts.json", {})
    ev = {"concept": args.concept, "type": args.type,
          "area": args.area, "name": args.name, "note": args.note}
    cid = apply_event(concepts, ev)
    if not cid:
        sys.exit("invalid concept id")
    save("concepts.json", concepts)
    append_event_log([{"ts": now_iso(), "session": "live", "concept": cid,
                       "type": args.type, "note": (args.note or "")[:200]}])
    c = concepts[cid]
    print(f"{cid}: rating {c['rating']:.2f} ({c['evidence']} pieces of evidence)")


def cmd_add_review(args):
    reviews = load("reviews.json", [])
    rid = add_review_card(reviews, args.concept, args.question, args.hint, "live")
    if rid:
        save("reviews.json", reviews)
        print(f"recall card {rid} added, due in 2 days")
    else:
        print("duplicate card, skipped")


# ---------------------------------------------------------------- recall

def cmd_due(args):
    reviews = load("reviews.json", [])
    t = today().isoformat()
    due = sorted((r for r in reviews if r["due"] <= t), key=lambda r: r["due"])
    future = sorted((r["due"] for r in reviews if r["due"] > t))
    print(json.dumps({
        "due": due[:args.limit],
        "count_due": len(due),
        "next_due": future[0] if future else None,
    }, indent=2))


def cmd_grade(args):
    reviews = load("reviews.json", [])
    item = next((r for r in reviews if r["id"] == args.id), None)
    if not item:
        sys.exit(f"no recall card with id {args.id}")
    if args.grade == "correct":
        item["interval"] = max(3, round(item["interval"] * 2.2))
    elif args.grade == "partial":
        item["interval"] = max(2, round(item["interval"] * 1.3))
    else:
        item["interval"] = 1
    item["due"] = (today() + dt.timedelta(days=item["interval"])).isoformat()
    item["reps"] += 1
    save("reviews.json", reviews)

    concepts = load("concepts.json", {})
    cid = apply_event(concepts, {"concept": item["concept"],
                                 "type": "review_" + args.grade})
    if cid:
        save("concepts.json", concepts)
        append_event_log([{"ts": now_iso(), "session": "recall", "concept": cid,
                           "type": "review_" + args.grade,
                           "note": item["question"][:120]}])
        rating = f"; {item['concept']} rating {concepts[cid]['rating']:.2f}"
    else:
        rating = ""
    print(f"{item['id']} -> {args.grade}; next due {item['due']}{rating}")


# ---------------------------------------------------------------- reporting

def cmd_stats(args):
    settings = load("settings.json", {})
    concepts = load("concepts.json", {})
    reviews = load("reviews.json", [])
    cutoff = (dt.datetime.now(dt.timezone.utc)
              - dt.timedelta(days=args.days)).isoformat(timespec="seconds")

    touched = {}
    total = 0
    for e in read_event_log():
        if e.get("ts", "") < cutoff:
            continue
        total += 1
        c = touched.setdefault(e["concept"], {"types": {}, "notes": []})
        c["types"][e["type"]] = c["types"].get(e["type"], 0) + 1
        if e.get("note") and len(c["notes"]) < 3:
            c["notes"].append(e["note"])
    for cid, info in touched.items():
        info["rating"] = concepts.get(cid, {}).get("rating")

    ranked = sorted(concepts.items(), key=lambda kv: kv[1]["rating"])
    t = today().isoformat()
    print(json.dumps({
        "calibrated": bool(settings.get("calibrated")),
        "mode": settings.get("mode", "active"),
        "window_days": args.days,
        "events_in_window": total,
        "concepts_touched": touched,
        "weakest": [{"concept": cid, **c} for cid, c in ranked[:5]],
        "strongest": [{"concept": cid, **c} for cid, c in ranked[-5:][::-1]],
        "recall_due": sum(1 for r in reviews if r["due"] <= t),
        "recall_total": len(reviews),
    }, indent=2))


# ---------------------------------------------------------------- settings

# ---------------------------------------------------------------- goals

GOAL_TYPES = ("skill", "project", "direction", "habit")


def goal_concept_ids(goal, concepts):
    """All concept ids a goal is measured against (explicit + area-derived)."""
    ids = set(c for c in (goal.get("concepts") or []) if isinstance(c, str))
    areas = set(a for a in (goal.get("areas") or []) if a in AREAS)
    if areas:
        ids |= {cid for cid, c in concepts.items() if c.get("area") in areas}
    return ids


def cmd_goal_add(args):
    """Read a goal object (or {"goals": [...]}) from stdin and append it.

    Snapshots current ratings of the linked concepts as a baseline so progress
    can be measured from the moment the goal is set.
    """
    data = parse_llm_json(sys.stdin.read())
    incoming = data["goals"] if isinstance(data.get("goals"), list) else [data]
    goals = load("goals.json", [])
    concepts = load("concepts.json", {})
    added = 0
    for g in incoming:
        if not isinstance(g, dict) or not g.get("text"):
            continue
        gid = hashlib.sha1(str(g["text"]).encode()).hexdigest()[:8]
        if any(x["id"] == gid for x in goals):
            continue
        goal = {
            "id": gid,
            "text": str(g["text"])[:300],
            "type": g["type"] if g.get("type") in GOAL_TYPES else "direction",
            "concepts": [c for c in (g.get("concepts") or []) if isinstance(c, str)],
            "areas": [a for a in (g.get("areas") or []) if a in AREAS],
            "target": (round(clamp(float(g["target"]), 0.2, 5.0), 2)
                       if isinstance(g.get("target"), (int, float)) else None),
            "why": str(g.get("why") or "")[:300],
            "horizon": str(g.get("horizon") or ""),
            "created": today().isoformat(),
            "status": "active",
        }
        cids = goal_concept_ids(goal, concepts)
        goal["baseline"] = {cid: concepts[cid]["rating"]
                            for cid in cids if cid in concepts}
        goals.append(goal)
        added += 1
    save("goals.json", goals)
    active = sum(1 for g in goals if g["status"] == "active")
    print(f"added {added} goal(s); {active} active")


def cmd_goal_list(args):
    print(json.dumps(load("goals.json", []), indent=2))


def cmd_goal_status(args):
    goals = load("goals.json", [])
    g = next((x for x in goals if x["id"] == args.id), None)
    if not g:
        sys.exit(f"no goal with id {args.id}")
    g["status"] = args.status
    save("goals.json", goals)
    print(f"{args.id} -> {args.status}")


def cmd_goal_check(args):
    """Score recent activity against active goals. The alignment question:
    is your real work moving you toward what you said you wanted?"""
    goals = [g for g in load("goals.json", []) if g.get("status") == "active"]
    concepts = load("concepts.json", {})
    metrics = load("metrics.json", {})
    cutoff = (dt.datetime.now(dt.timezone.utc)
              - dt.timedelta(days=args.days)).isoformat(timespec="seconds")

    recent, total_recent = {}, 0
    for e in read_event_log():
        if e.get("ts", "") < cutoff:
            continue
        total_recent += 1
        recent[e["concept"]] = recent.get(e["concept"], 0) + 1

    goal_cids, reports = set(), []
    for g in goals:
        cids = goal_concept_ids(g, concepts)
        goal_cids |= cids
        rated = [concepts[c] for c in cids if c in concepts]
        ev = sum(c["evidence"] for c in rated)
        cur = round(sum(c["rating"] * c["evidence"] for c in rated) / ev, 2) if ev else None
        base_vals = [g["baseline"][c] for c in cids if c in g.get("baseline", {})]
        base = round(sum(base_vals) / len(base_vals), 2) if base_vals else None
        delta = round(cur - base, 2) if cur is not None and base is not None else None
        activity = sum(recent.get(c, 0) for c in cids)

        if not cids:
            verdict = "guidance goal — shapes sessions, not scored"
        elif cur is None:
            verdict = (f"active — {activity} recent events touched this" if activity
                       else f"no work in {args.days}d")
        elif g.get("target") and cur >= g["target"]:
            verdict = "achieved"
        elif activity == 0:
            verdict = f"stalled — no work in {args.days}d"
        elif delta is not None and delta > 0.05:
            verdict = f"on track (+{delta} since set)"
        elif delta is not None and delta < -0.05:
            verdict = "slipping"
        else:
            verdict = "active but rating flat — try hands-on / prediction"
        goal_metrics = {}
        for key in (g.get("metrics") or []):
            mcur, mdelta = metric_delta(metrics, key,
                                        g.get("created", "") + "T00:00:00+00:00")
            goal_metrics[key] = {"current": mcur, "since_set": mdelta}
        report = {"id": g["id"], "text": g["text"], "type": g["type"],
                  "current": cur, "baseline": base, "target": g.get("target"),
                  "delta": delta, "recent_events": activity, "verdict": verdict}
        if goal_metrics:
            report["outcome_metrics"] = goal_metrics
        reports.append(report)

    aligned = sum(recent.get(c, 0) for c in goal_cids)
    off = {}
    for cid, n in recent.items():
        if cid in goal_cids:
            continue
        a = concepts.get(cid, {}).get("area", "other")
        off[a] = off.get(a, 0) + n
    print(json.dumps({
        "window_days": args.days,
        "recent_events": total_recent,
        "goal_aligned_events": aligned,
        "alignment_pct": round(100 * aligned / total_recent) if total_recent else None,
        "top_off_goal_areas": sorted(off.items(), key=lambda kv: -kv[1])[:4],
        "goals": reports,
    }, indent=2))


# ---------------------------------------------------------------- paths
#
# A learning path is a curated, ordered curriculum — a sequence of concepts with
# per-step targets. It turns the reactive model (learn what you happen to touch)
# into a directed one (walk this route), and steers the mentor step by step.

def cmd_path_add(args):
    """Read {"title": ..., "steps": [{concept, area?, target?, note?}]} from stdin."""
    data = parse_llm_json(sys.stdin.read())
    title = str(data.get("title") or "").strip()
    steps_in = data.get("steps") or []
    if not title or not isinstance(steps_in, list) or not steps_in:
        sys.exit("need a title and a non-empty steps list")
    steps = []
    for s in steps_in:
        if not isinstance(s, dict) or not s.get("concept"):
            continue
        steps.append({
            "concept": norm_concept(str(s["concept"])),
            "area": s["area"] if s.get("area") in AREAS else "other",
            "target": (round(clamp(float(s["target"]), 0.2, 5.0), 2)
                       if isinstance(s.get("target"), (int, float)) else 3.5),
            "note": str(s.get("note") or "")[:160],
        })
    if not steps:
        sys.exit("no valid steps")
    paths = load("paths.json", [])
    pid = hashlib.sha1(title.encode()).hexdigest()[:8]
    paths = [p for p in paths if p["id"] != pid]  # replace same-title path
    paths.append({"id": pid, "title": title[:120], "steps": steps,
                  "created": today().isoformat(), "status": "active"})
    save("paths.json", paths)
    print(f"path '{title}' saved ({len(steps)} steps), id {pid}")


def cmd_path_list(args):
    print(json.dumps(load("paths.json", []), indent=2))


def cmd_path_status(args):
    paths = load("paths.json", [])
    p = next((x for x in paths if x["id"] == args.id), None)
    if not p:
        sys.exit(f"no path {args.id}")
    p["status"] = args.status
    save("paths.json", paths)
    print(f"{args.id} -> {args.status}")


def path_progress(path, concepts):
    """Annotate each step with current rating and whether the target is met."""
    steps, met = [], 0
    nxt = None
    for s in steps_iter(path):
        cur = concepts.get(s["concept"], {}).get("rating")
        done = cur is not None and cur >= s["target"]
        if done:
            met += 1
        elif nxt is None:
            nxt = s["concept"]
        steps.append({**s, "current": cur, "met": done})
    total = len(steps) or 1
    return {"id": path["id"], "title": path["title"],
            "pct": round(100 * met / total), "met": met, "total": len(steps),
            "next": nxt, "steps": steps}


def steps_iter(path):
    return path.get("steps", [])


def cmd_path_progress(args):
    concepts = load("concepts.json", {})
    active = [p for p in load("paths.json", []) if p.get("status") == "active"]
    print(json.dumps([path_progress(p, concepts) for p in active], indent=2))


def cmd_review_bulk(args):
    """Load many quiz cards at once: stdin {"cards": [{concept, question, hint?}]}."""
    data = parse_llm_json(sys.stdin.read())
    cards = data.get("cards") or []
    reviews = load("reviews.json", [])
    added = 0
    for c in cards[:30]:
        if not (isinstance(c, dict) and isinstance(c.get("concept"), str)
                and isinstance(c.get("question"), str)):
            continue
        if add_review_card(reviews, c["concept"], c["question"],
                           str(c.get("hint") or ""), args.source):
            added += 1
    save("reviews.json", reviews)
    print(f"added {added} quiz card(s)")


# ---------------------------------------------------------------- metrics
#
# Outcome metrics close the loop the learning model can't reach on its own:
# GitHub stars, revenue, social — the real-world results your work is aiming at.
# Stored as a flat dict of {key: {"history": [{ts, value}]}} time series.

def metric_append(metrics, key, value, ts=None, note=""):
    h = metrics.setdefault(key, {"history": []})["history"]
    entry = {"ts": ts or now_iso(), "value": value}
    if note:
        entry["note"] = note[:120]
    h.append(entry)
    del h[:-500]  # bound history


def metric_current(metrics, key):
    h = metrics.get(key, {}).get("history", [])
    return h[-1]["value"] if h else None


def metric_delta(metrics, key, since_iso):
    """Return (current, change since the last snapshot at/before since_iso)."""
    h = metrics.get(key, {}).get("history", [])
    if not h:
        return None, None
    cur = h[-1]["value"]
    base = next((e["value"] for e in reversed(h) if e["ts"] <= since_iso),
                h[0]["value"])
    delta = (round(cur - base, 2)
             if isinstance(cur, (int, float)) and isinstance(base, (int, float))
             else None)
    return cur, delta


def cmd_metric_github(args):
    """Read repo JSONL ({name,stars,forks,issues}) from stdin; snapshot totals
    plus per-repo counts for anything with traction."""
    total_stars = total_forks = total_issues = 0
    per_repo = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        s, f = int(r.get("stars") or 0), int(r.get("forks") or 0)
        total_stars += s
        total_forks += f
        total_issues += int(r.get("issues") or 0)
        if (s or f) and r.get("name"):
            per_repo.append((r["name"], s, f))
    metrics = load("metrics.json", {})
    ts = now_iso()
    metric_append(metrics, "github.stars.total", total_stars, ts)
    metric_append(metrics, "github.forks.total", total_forks, ts)
    metric_append(metrics, "github.open_issues.total", total_issues, ts)
    for name, s, _ in per_repo:
        metric_append(metrics, f"github.stars.{name}", s, ts)
    save("metrics.json", metrics)
    print(f"github snapshot: {total_stars} stars, {total_forks} forks "
          f"across {len(per_repo)} repos with traction")


def cmd_metric_record(args):
    """Manually record an outcome metric (revenue, followers, anything numeric)."""
    try:
        value = float(args.value)
    except ValueError:
        sys.exit("value must be numeric")
    value = int(value) if value == int(value) else round(value, 2)
    metrics = load("metrics.json", {})
    metric_append(metrics, args.key, value, note=args.note)
    save("metrics.json", metrics)
    cur, delta = metric_delta(metrics, args.key,
                              (dt.datetime.now(dt.timezone.utc)
                               - dt.timedelta(days=30)).isoformat(timespec="seconds"))
    print(f"{args.key}: {value} recorded"
          + (f" ({delta:+g} over 30d)" if delta else ""))


def cmd_metric_report(args):
    metrics = load("metrics.json", {})
    since = (dt.datetime.now(dt.timezone.utc)
             - dt.timedelta(days=args.days)).isoformat(timespec="seconds")
    out = {}
    for key in sorted(metrics):
        cur, delta = metric_delta(metrics, key, since)
        out[key] = {"current": cur, f"change_{args.days}d": delta,
                    "snapshots": len(metrics[key]["history"])}
    print(json.dumps({"window_days": args.days, "metrics": out}, indent=2))


# ---------------------------------------------------------------- serve

RECALL_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Recall</title>
<style>
 :root{color-scheme:light dark;--bg:#0c1416;--panel:#121e20;--ink:#e7efeb;--muted:#8ba09a;
  --line:#20302f;--accent:#3fc0af;--do:#79c96b;--warn:#e0a740;--bad:#e06a5a}
 @media(prefers-color-scheme:light){:root{--bg:#eaece9;--panel:#f6f7f4;--ink:#15201e;
  --muted:#5c6c68;--line:#d2d9d3;--accent:#0f8477;--do:#3f9a52;--warn:#bd7f1f;--bad:#c0503f}}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.6 ui-sans-serif,system-ui,-apple-system,sans-serif;min-height:100vh;
  display:flex;flex-direction:column;align-items:center;padding:40px 20px}
 .mono{font-family:ui-monospace,"SF Mono",Menlo,monospace}
 a{color:var(--accent)} .wrap{width:100%;max-width:640px}
 .eyebrow{font:600 12px/1 ui-monospace,monospace;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);margin-bottom:20px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:30px 28px;box-shadow:0 14px 40px -22px rgba(0,0,0,.6)}
 .meta{font-family:ui-monospace,monospace;font-size:12px;color:var(--muted);margin-bottom:16px;display:flex;justify-content:space-between}
 .q{font-size:20px;line-height:1.45;margin:0 0 20px;text-wrap:balance}
 .hint{color:var(--muted);font-size:14.5px;margin:0 0 22px;padding-left:14px;border-left:2px solid var(--line)}
 .hidden{display:none}
 button{font:600 14px ui-sans-serif,system-ui,sans-serif;border:1px solid var(--line);
  background:var(--panel);color:var(--ink);border-radius:10px;padding:11px 16px;cursor:pointer}
 button:hover{border-color:var(--accent)} button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
 .reveal{width:100%;margin-bottom:4px}
 .grades{display:flex;gap:10px;margin-top:8px}.grades button{flex:1}
 .g-correct{border-color:var(--do);color:var(--do)} .g-partial{border-color:var(--warn);color:var(--warn)}
 .g-incorrect{border-color:var(--bad);color:var(--bad)}
 .done{text-align:center;color:var(--muted);padding:50px 0}
 .nav{margin-top:24px;font-size:13px;color:var(--muted);text-align:center}
</style></head><body><div class="wrap">
 <div class="eyebrow">› spaced recall</div>
 <div id="app"></div>
 <div class="nav"><a href="/">← back to dashboard</a></div>
</div>
<script>
let cards=[],i=0;
const app=document.getElementById("app");
async function load(){const r=await fetch("/api/due");const d=await r.json();cards=d.due||[];i=0;render();}
function render(){
 if(i>=cards.length){app.innerHTML=`<div class="done"><p style="font-size:20px">✓ All caught up.</p>
   <p>${cards.length} card${cards.length===1?"":"s"} reviewed. Next batch surfaces as it comes due.</p></div>`;return;}
 const c=cards[i];
 app.innerHTML=`<div class="card">
   <div class="meta"><span class="mono">${c.concept}</span><span class="mono">${i+1} / ${cards.length}</span></div>
   <p class="q">${esc(c.question)}</p>
   ${c.hint?`<p class="hint hidden" id="hint">💡 ${esc(c.hint)}</p>`:""}
   <button class="reveal" id="rev">Think first, then reveal hint &amp; grade</button>
   <div class="grades hidden" id="grades">
     <button class="g-incorrect" data-g="incorrect">Missed</button>
     <button class="g-partial" data-g="partial">Partial</button>
     <button class="g-correct" data-g="correct">Got it</button>
   </div></div>`;
 const rev=document.getElementById("rev");
 rev.onclick=()=>{const h=document.getElementById("hint");if(h)h.classList.remove("hidden");
   document.getElementById("grades").classList.remove("hidden");rev.classList.add("hidden");};
 document.querySelectorAll("#grades button").forEach(b=>b.onclick=async()=>{
   await fetch("/api/grade",{method:"POST",headers:{"Content-Type":"application/json"},
     body:JSON.stringify({id:c.id,grade:b.dataset.g})});i++;render();});
}
function esc(s){const d=document.createElement("div");d.textContent=s;return d.innerHTML;}
load();
</script></body></html>"""


def cmd_serve(args):
    import http.server
    import socketserver
    import subprocess
    import tempfile

    scripts_dir = os.path.dirname(SCRIPT)
    today_iso = today().isoformat()

    def dashboard_html():
        tmp = os.path.join(tempfile.gettempdir(), "cl-journey.html")
        try:
            r = subprocess.run([sys.executable, os.path.join(scripts_dir, "journey.py"), tmp],
                               capture_output=True, text=True, timeout=30,
                               env={**os.environ, "CL_HOME": CL_HOME})
            if r.returncode == 0 and os.path.exists(tmp):
                with open(tmp, encoding="utf-8") as f:
                    return f.read()
            return f"<h1>continuous-learning</h1><p>No journey yet: {r.stdout or r.stderr}</p>"
        except Exception as e:
            return f"<h1>continuous-learning</h1><p>{e}</p>"

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, ctype="application/json", code=200):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                self._send(dashboard_html(), "text/html; charset=utf-8")
            elif self.path == "/recall":
                self._send(RECALL_HTML, "text/html; charset=utf-8")
            elif self.path == "/api/due":
                reviews = load("reviews.json", [])
                due = sorted((r for r in reviews if r["due"] <= today_iso),
                             key=lambda r: r["due"])[:20]
                self._send(json.dumps({"due": due, "count": len(due)}))
            else:
                self._send(json.dumps({"error": "not found"}), code=404)

        def do_POST(self):
            if self.path != "/api/grade":
                return self._send(json.dumps({"error": "not found"}), code=404)
            length = int(self.headers.get("Content-Length", 0) or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._send(json.dumps({"error": "bad json"}), code=400)
            rid, grade = payload.get("id"), payload.get("grade")
            if grade not in ("correct", "partial", "incorrect"):
                return self._send(json.dumps({"error": "bad grade"}), code=400)
            reviews = load("reviews.json", [])
            item = next((r for r in reviews if r["id"] == rid), None)
            if not item:
                return self._send(json.dumps({"error": "no card"}), code=404)
            if grade == "correct":
                item["interval"] = max(3, round(item["interval"] * 2.2))
            elif grade == "partial":
                item["interval"] = max(2, round(item["interval"] * 1.3))
            else:
                item["interval"] = 1
            item["due"] = (today() + dt.timedelta(days=item["interval"])).isoformat()
            item["reps"] += 1
            save("reviews.json", reviews)
            concepts = load("concepts.json", {})
            cid = apply_event(concepts, {"concept": item["concept"],
                                         "type": "review_" + grade})
            if cid:
                save("concepts.json", concepts)
                append_event_log([{"ts": now_iso(), "session": "serve",
                                   "concept": cid, "type": "review_" + grade,
                                   "note": item["question"][:120]}])
            self._send(json.dumps({"ok": True, "next_due": item["due"]}))

    class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    httpd = Server(("127.0.0.1", args.port), H)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"continuous-learning dashboard → {url}")
    print(f"  recall quiz → {url}recall")
    print("local only (127.0.0.1), no auth. Ctrl-C to stop.")
    if args.open:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


def cmd_seed(args):
    """Merge stdin JSON {"mode": ..., "concepts": {id: {rating, area, name}}}."""
    data = parse_llm_json(sys.stdin.read())
    concepts = load("concepts.json", {})
    settings = load("settings.json", {})
    n = 0
    for cid, spec in (data.get("concepts") or {}).items():
        if not isinstance(spec, dict) or "rating" not in spec:
            continue
        try:
            rating = round(clamp(float(spec["rating"]), 0.2, 5.0), 2)
        except (TypeError, ValueError):
            continue  # one bad rating must not abort the whole calibration
        cid = norm_concept(str(cid))
        old = concepts.get(cid, {})
        concepts[cid] = {
            "name": spec.get("name") or old.get("name") or cid.replace("-", " "),
            "area": spec.get("area") if spec.get("area") in AREAS
                    else old.get("area", "other"),
            "rating": rating,
            "evidence": max(1, old.get("evidence", 0)),
            "last_seen": now_iso(),
        }
        n += 1
    settings["calibrated"] = True
    if data.get("mode") in MODES:
        settings["mode"] = data["mode"]
    save("concepts.json", concepts)
    save("settings.json", settings)
    print(f"seeded {n} concepts; mode={settings.get('mode', 'active')}; calibrated=true")


def cmd_set_mode(args):
    settings = load("settings.json", {})
    settings["mode"] = args.mode
    save("settings.json", settings)
    print(f"mentor mode set to {args.mode}")


def cmd_get_mode(args):
    print(load("settings.json", {}).get("mode", "active"))


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(prog="cl.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("hook-session-start").set_defaults(fn=cmd_hook_session_start)
    sub.add_parser("hook-stop").set_defaults(fn=cmd_hook_stop)
    sub.add_parser("queue-pending").set_defaults(fn=cmd_queue_pending)
    s = sub.add_parser("queue-done")
    s.add_argument("session_id")
    s.set_defaults(fn=cmd_queue_done)
    s = sub.add_parser("attempt")
    s.add_argument("session_id")
    s.set_defaults(fn=cmd_attempt)
    s = sub.add_parser("queue-add")
    s.add_argument("session_id")
    s.add_argument("transcript_path")
    s.set_defaults(fn=cmd_queue_add)

    s = sub.add_parser("digest-transcript")
    s.add_argument("transcript")
    s.set_defaults(fn=cmd_digest_transcript)

    s = sub.add_parser("apply-events")
    s.add_argument("--session", default="unknown")
    s.add_argument("--ts", default=None,
                   help="ISO timestamp the session actually happened (backfill)")
    s.set_defaults(fn=cmd_apply_events)

    s = sub.add_parser("log-event")
    s.add_argument("--concept", required=True)
    s.add_argument("--type", required=True, choices=sorted(NUDGES))
    # not choices-restricted: apply_event coerces unknown areas to "other",
    # and losing the evidence over a label would be the wrong trade
    s.add_argument("--area", default="other")
    s.add_argument("--name", default=None)
    s.add_argument("--note", default="")
    s.set_defaults(fn=cmd_log_event)

    s = sub.add_parser("add-review")
    s.add_argument("--concept", required=True)
    s.add_argument("--question", required=True)
    s.add_argument("--hint", default="")
    s.set_defaults(fn=cmd_add_review)

    s = sub.add_parser("due")
    s.add_argument("--limit", type=int, default=7)
    s.set_defaults(fn=cmd_due)

    s = sub.add_parser("grade")
    s.add_argument("id")
    s.add_argument("grade", choices=("correct", "partial", "incorrect"))
    s.set_defaults(fn=cmd_grade)

    s = sub.add_parser("stats")
    s.add_argument("--days", type=int, default=7)
    s.set_defaults(fn=cmd_stats)

    sub.add_parser("metric-github").set_defaults(fn=cmd_metric_github)
    s = sub.add_parser("metric-record")
    s.add_argument("key")
    s.add_argument("value")
    s.add_argument("--note", default="")
    s.set_defaults(fn=cmd_metric_record)
    s = sub.add_parser("metric-report")
    s.add_argument("--days", type=int, default=30)
    s.set_defaults(fn=cmd_metric_report)

    sub.add_parser("goal-add").set_defaults(fn=cmd_goal_add)
    sub.add_parser("goal-list").set_defaults(fn=cmd_goal_list)
    s = sub.add_parser("goal-status")
    s.add_argument("id")
    s.add_argument("status", choices=("active", "done", "paused"))
    s.set_defaults(fn=cmd_goal_status)
    s = sub.add_parser("goal-check")
    s.add_argument("--days", type=int, default=14)
    s.set_defaults(fn=cmd_goal_check)

    sub.add_parser("path-add").set_defaults(fn=cmd_path_add)
    sub.add_parser("path-list").set_defaults(fn=cmd_path_list)
    s = sub.add_parser("path-status")
    s.add_argument("id")
    s.add_argument("status", choices=("active", "done", "paused"))
    s.set_defaults(fn=cmd_path_status)
    sub.add_parser("path-progress").set_defaults(fn=cmd_path_progress)
    s = sub.add_parser("review-bulk")
    s.add_argument("--source", default="quiz")
    s.set_defaults(fn=cmd_review_bulk)

    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8787)
    s.add_argument("--open", action="store_true")
    s.set_defaults(fn=cmd_serve)

    sub.add_parser("seed").set_defaults(fn=cmd_seed)

    s = sub.add_parser("set-mode")
    s.add_argument("mode", choices=MODES)
    s.set_defaults(fn=cmd_set_mode)

    sub.add_parser("get-mode").set_defaults(fn=cmd_get_mode)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
