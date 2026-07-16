# Continuous Learning

A mentor layer for [Claude Code](https://claude.com/claude-code). You keep doing real
work — fixing configs, writing scripts, debugging CI — and the plugin turns that work
into education: it profiles what you know per concept, teaches through **targeted,
optional** interactions calibrated to your level, and closes the loop with spaced
repetition built from your own sessions.

Think driving instructor with dual controls, not driving school with a textbook.

## How it works

```text
 session start                 during the session                session end
┌─────────────────┐   ┌───────────────────────────────┐   ┌─────────────────────┐
│ SessionStart    │   │ Claude works normally, plus:  │   │ SessionEnd hook     │
│ hook injects    │──▶│ · 1-sentence asides on weak   │──▶│ backgrounds a cheap │
│ your learner    │   │   concepts, silence on strong │   │ model call over the │
│ model + rules   │   │ · ≤2 optional end-of-turn     │   │ transcript, extracts│
└─────────────────┘   │   micro-checks (predictions)  │   │ learning events     │
        ▲             │ · logs evidence as it appears │   └──────────┬──────────┘
        │             └───────────────────────────────┘              │
        │                                                            ▼
┌───────┴──────────┐        ┌──────────────────┐        ┌─────────────────────┐
│ concepts.json    │◀───────│ events.jsonl     │◀───────│ per-concept rating  │
│ per-concept      │        │ append-only      │        │ nudges + recall     │
│ ratings 0–5      │        │ evidence log     │        │ card creation       │
└──────────────────┘        └──────────────────┘        └─────────────────────┘
```

- **Learner model** — every concept (e.g. `git-rebase`, `dns-cname-records`) gets a
  0–5 rating updated Elo-style by evidence: asking a basic question nudges it down,
  a correct prediction or hands-on win nudges it up, first evidence counts double,
  and ratings decay slowly after 60 idle days. No single "level 7 sysadmin" score —
  levels are per concept.
- **Passive profiling** — most evidence is harvested from what the work already
  reveals (the vocabulary you use, the questions you ask, what you did yourself),
  not from quizzes.
- **Targeted optional interaction** — at most two micro-checks per session, only at
  the end of a completed turn, always ignorable at zero cost. Ignore one and the
  mentor stands down; say "just do it" and teaching suspends for the session.
- **Spaced repetition from real work** — recall cards are generated from things that
  actually happened ("when you fixed that CORS error, what were the two headers?"),
  scheduled SM-2-style: 2 days, then ~2× on success, reset on a miss.

## Install

```bash
# inside Claude Code
/plugin marketplace add <path-to-this-repo>   # or a GitHub URL once published
/plugin install continuous-learning@continuous-learning
```

Then in a new session run `/continuous-learning:profile` — a one-minute
conversational calibration (never a placement test). It only needs to be roughly
right; ratings self-correct from real evidence within a few sessions.

### Backfill from your existing history

Instead of (or in addition to) the interview, seed the learner model from the
Claude Code sessions you've already had:

```bash
scripts/backfill.sh        # all past sessions, oldest first
scripts/backfill.sh 20     # or cap per run to pace quota usage
```

Events are stamped with each session's real date (so stats windows and decay
stay honest), sessions older than 14 days don't mint recall cards (a "remember
yesterday?" card about last month would be confusing), and already-processed
sessions are skipped, so re-running is always safe.

### Local extraction with Ollama

Extraction defaults to a small headless `claude -p --model haiku` call
(override the model with `CL_EXTRACT_MODEL`). To keep transcripts entirely on
your machine — and off your API quota — point `CL_EXTRACT_CMD` at any command
that reads a prompt on stdin and prints JSON:

```bash
CL_EXTRACT_CMD="ollama run qwen2.5-coder:32b" scripts/backfill.sh
```

The parser tolerates noisier local-model output; malformed events are dropped
rather than breaking the pipeline.

## Commands

| Command | What it does |
|---|---|
| `/continuous-learning:profile` | View or calibrate your learner profile |
| `/continuous-learning:mentor <mode>` | Set mode: `off`, `quiet`, `active`, `coach` |
| `/continuous-learning:recall` | Spaced-repetition quiz from your own recent work |
| `/continuous-learning:quiz <topic>` | Generate a targeted quiz on a topic and load it into recall |
| `/continuous-learning:path` | Create and track a learning path — a curated curriculum |
| `/continuous-learning:digest [days]` | What you touched, where you wobbled, one exercise |
| `/continuous-learning:goals` | Set goals and check whether your real work is heading toward them |
| `/continuous-learning:metrics` | Track real-world outcomes (GitHub stars, revenue, social) and tie them to goals |
| `/continuous-learning:capture-study` | Log what you learned outside Claude (from your activity history) |
| `/continuous-learning:journey` | Render a shareable visual of your whole learning history |

Plus a local dashboard — run `python3 scripts/cl.py serve --open` for a live
version of the journey page and an in-browser recall quiz (localhost only, no auth).

### Reactive → directed

Recall auto-generates cards from what you happened to do. **Paths** and
**quizzes** let you drive: a path is an ordered concept curriculum with per-step
targets (its current step is injected into every session so the mentor leans in),
and a quiz drills any topic on demand into the same spaced-repetition schedule.
A separate `self_study` event type records learning you did *outside* Claude —
studying the docs yourself — as distinct from being taught by the assistant.

### Goals — descriptive → directional

The learner model tells you *where you are*. Goals add *where you're going*. Each
goal is injected into every session so the mentor nudges toward it, and the
**alignment check** (`/continuous-learning:goals check`) scores your recent
activity against what you said you wanted — comparing stated intent to how you
actually spent your sessions, which is the one thing a to-do list can't do. The
headline is a single `alignment_pct`: the share of recent work that advanced a
goal. Skill goals also track a rating **delta** from a baseline snapshotted when
you set the goal, so "am I actually getting better at this?" has a number.
Goals live in `~/.continuous-learning/goals.json`, editable like everything else.

### Outcome metrics — closing the loop

Goals like "grow audience" or "reach revenue" aren't about a skill rating — they
have real-world numbers. The metrics layer tracks those as time series in
`metrics.json`, and a goal can link one so the check reports it directly ("276
stars, +14 since you set this"). GitHub (stars, forks, per-repo, optional
traffic) is pulled automatically via the `gh` CLI — on demand with
`scripts/metrics.sh`, and opportunistically (throttled to ~daily) at session
end. Revenue and social have no universal API, so they're one-line manual
entries (`cl.py metric-record revenue.total 500`) whose trend builds from what
you record. See `/continuous-learning:metrics`.

Modes: **quiet** observes and logs but never interjects; **active** (default) adds
calibrated asides and optional checks; **coach** additionally leaves small safe
pieces of tasks for you, with hints; **off** disables everything.

## Data & privacy

Everything is local, human-readable, and yours to edit or delete:

```text
~/.continuous-learning/        # override with $CL_HOME
├── profile.md        # narrative: who you are, goals, context for explanations
├── settings.json     # mode, calibrated flag
├── concepts.json     # per-concept ratings + evidence counts
├── events.jsonl      # append-only log of learning events
├── reviews.json      # spaced-repetition recall cards
├── goals.json        # goals + the direction they steer toward
├── paths.json        # learning paths (ordered concept curricula)
├── metrics.json      # outcome-metric time series (GitHub stars, revenue, …)
├── queue.txt         # sessions awaiting extraction
├── queue.done.txt    # sessions already extracted (dedupe ledger)
├── queue.attempts    # extraction retry counts
└── logs/             # extraction pipeline logs (plus a transient extract.lock/)
```

To reset everything, delete the whole directory (`rm -rf ~/.continuous-learning`) —
pruning individual queue files changes what gets (re-)extracted in non-obvious ways.

The only network use is the extraction step, which calls `claude -p` (a small
headless request with your existing Claude Code auth; model override:
`CL_EXTRACT_MODEL`, default `haiku`). Disputing your own ratings is encouraged —
open `/continuous-learning:profile` and argue; corrections are evidence too.

## Design notes

- **Teaching friction kills adoption**, so every intervention is skippable in one
  keystroke and the mentor teaches less as evidence accumulates that it will get
  another chance (the recall loop makes missed moments deferred, not lost).
- **Prediction beats recall** both for learning and for profiling — checks are
  phrased as "what will happen?" wherever possible.
- Extraction runs in the background at session end and is guarded against recursion
  (`CL_EXTRACT`), locking (single instance), and tiny sessions (skipped).

Known limitations (v0.1): a session resumed after its transcript was already
extracted is not re-extracted; a transcript that fails extraction is retried up to
3 times, then dropped (watch `logs/extract.log`).

## Development

```bash
# run the data layer against a throwaway home
export CL_HOME=/tmp/cl-test
python3 scripts/cl.py log-event --concept git-rebase --area git --type struggled --note "test"
python3 scripts/cl.py stats --days 7
```

MIT licensed. Contributions welcome — the interesting frontiers are richer knowledge
tracing (BKT/IRT instead of Elo nudges), a concept-graph visualization, and
multi-provider extraction.
