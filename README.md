# Continuous Learning

**Your Claude Code sessions are training data — about you, not the model.**
A local-first [Claude Code](https://claude.com/claude-code) plugin that turns your
real work into a personal learning system: it learns what you know per concept,
teaches through *targeted, optional* nudges, and closes the loop with recall,
goals, and a shareable picture of your progress.

`local-first` · `MIT` · `stdlib-only` · `Claude Code plugin`

Think driving instructor with dual controls, not driving school with a textbook.

---

## What you get

- **A per-concept skill model** — a 0–5 rating for `systemd-units`, `supabase-rls`,
  `git-rebase`… nudged by evidence from your actual sessions. No single "level 7"
  score; levels are per concept.
- **Teaching in the margins** — one calibrated sentence on a weak concept, silence
  on a strong one, ≤2 optional prediction-checks per session. All skippable; "just
  do it" turns it off. It never blocks the real work.
- **Spaced-repetition recall** — cards generated from things that actually happened
  ("when you fixed that CORS error, which two headers?"), on an SM-2 schedule.
- **Goals with an alignment check** — state where you're going; get a number for
  whether your real work is heading there.
- **Outcome metrics** — GitHub stars, revenue, social — so goals like "grow
  audience" get a real figure, not a vibe.
- **Learning paths & quizzes** — drive a curriculum on purpose, not just react.
- **A shareable visual journey** — your whole history as one page (or a live
  local dashboard).

Everything is local, human-readable JSON in a dotfolder you own. The only network
call is the extraction step — and you can point that at a local model.

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

The rating model is deliberately simple: asking a basic question nudges a concept
down, a correct prediction or hands-on win nudges it up, first evidence counts
double, and ratings decay slowly after 60 idle days. Most evidence is harvested
*passively* from what the work reveals — the vocabulary you use, the questions you
ask, what you did yourself — not from quizzes.

## Quickstart

```bash
# inside Claude Code
/plugin marketplace add jhammant/continuous-learning
/plugin install continuous-learning@continuous-learning
```

Then either calibrate conversationally —

```
/continuous-learning:profile     # ~1 min, never a placement test
```

— or seed the model from the sessions you've *already* had:

```bash
scripts/backfill.sh        # all past sessions, oldest first
scripts/backfill.sh 20     # or cap per run to pace quota usage
```

Backfill stamps each event with the session's real date, skips already-processed
sessions (safe to re-run), and won't mint stale recall cards from months ago.

**Keep it fully local.** Extraction defaults to a small `claude -p --model haiku`
call; point `CL_EXTRACT_CMD` at anything that reads a prompt on stdin and prints
JSON to keep transcripts on your machine and off your quota:

```bash
CL_EXTRACT_CMD="ollama run qwen2.5-coder:32b" scripts/backfill.sh
```

## Commands

| Command | What it does |
|---|---|
| `/continuous-learning:profile` | View or calibrate your learner profile |
| `/continuous-learning:mentor <mode>` | Set mode: `off`, `quiet`, `active`, `coach` |
| `/continuous-learning:recall` | Spaced-repetition quiz from your own recent work |
| `/continuous-learning:quiz <topic>` | Generate a targeted quiz and load it into recall |
| `/continuous-learning:path` | Create and track a learning path (curated curriculum) |
| `/continuous-learning:digest [days]` | **Written report** of a period — see below |
| `/continuous-learning:journey` | **Visual report** of your whole history — see below |
| `/continuous-learning:goals` | Set goals and check your work is heading toward them |
| `/continuous-learning:metrics` | Track outcomes (GitHub stars, revenue, social) |
| `/continuous-learning:capture-study` | Log what you learned *outside* Claude |
| `/continuous-learning:dashboard` | Open the live dashboard + in-browser recall in your browser |

Modes: **quiet** observes and logs but never interjects; **active** (default) adds
calibrated asides and optional checks; **coach** additionally leaves small safe
pieces of tasks for you, with hints; **off** disables everything.

## Reports & views

Reporting is done through slash commands (with a raw CLI underneath if you want to
script it):

| Want… | Run |
|---|---|
| A **written report** — what you touched, where you wobbled, one suggested exercise | `/continuous-learning:digest 7` (days) |
| A **visual report** of your whole journey (shareable HTML) | `/continuous-learning:journey` |
| A **live dashboard** + in-browser recall | `/continuous-learning:dashboard` |
| **Are you on track?** alignment of real work vs. stated goals | `/continuous-learning:goals check` |
| **Outcome trends** — stars/revenue over time | `/continuous-learning:metrics report` |
| **Raw JSON** to pipe into your own tooling | `python3 scripts/cl.py stats --days 30` |

So yes — the everyday report is the `/continuous-learning:digest` command, and
`/continuous-learning:journey` is its visual counterpart. Both read the same local
model; neither sends anything anywhere.

## The deeper loops

**Directed, not just reactive.** Recall auto-generates cards from what you happened
to do. **Paths** are ordered concept curricula with per-step targets (the current
step is injected into every session so the mentor leans in), and **quizzes** drill
any topic on demand into the same schedule. A `self_study` event type records
learning you did *outside* Claude — reading the docs yourself — as distinct from
being taught by the assistant.

**Goals turn "where am I" into "where am I going."** Each goal is injected into
every session so the mentor nudges toward it, and the alignment check scores your
recent activity against what you said you wanted — the one thing a to-do list
can't do. Skill goals track a rating **delta** from a baseline snapshotted when you
set the goal, so "am I actually getting better?" has a number.

**Outcome metrics close the loop.** Skill is the input; stars and revenue are the
output. GitHub is pulled automatically via the `gh` CLI (on demand and ~daily at
session end); revenue and social are one-line manual entries whose trend builds
from what you record. A goal can link a metric so the check reads "276 stars, +14
since you set this."

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
└── logs/             # extraction pipeline logs + queue ledgers
```

The only network use is the extraction step (`claude -p` by default, or your
`CL_EXTRACT_CMD`). Nothing else phones home. Disputing your own ratings is
encouraged — open `/continuous-learning:profile` and argue; corrections are
evidence too. To reset, delete the directory (`rm -rf ~/.continuous-learning`).

## Design notes

- **Teaching friction kills adoption**, so every intervention is skippable in one
  keystroke, and the mentor teaches *less* as it earns trust that a missed moment
  isn't lost — the recall loop just defers it.
- **Prediction beats recall** for both learning and profiling, so checks are phrased
  "what will happen?" wherever possible.
- Extraction runs in the background at session end, guarded against recursion,
  concurrent runs, and tiny sessions.

**Known limitations (v0.1):** a session resumed after extraction isn't
re-extracted; a transcript that fails extraction is retried 3× then dropped
(watch `logs/extract.log`); `retrace`-based web capture is app-level unless the
screen-capture source is enabled.

## Development & contributing

```bash
export CL_HOME=/tmp/cl-dev                       # a throwaway model
python3 scripts/cl.py seed <<< '{"concepts":{"git-rebase":{"rating":2,"area":"git"}}}'
python3 scripts/cl.py stats --days 7
python3 scripts/cl.py serve --open               # dashboard + browser recall
claude plugin validate .                         # before every PR
```

`cl.py` is dependency-free Python by design. The interesting frontiers: richer
knowledge tracing (BKT/IRT instead of Elo-style nudges), browser-side capture of
what you read, and first-class local-model extraction presets. See
[CONTRIBUTING.md](CONTRIBUTING.md). MIT licensed.
