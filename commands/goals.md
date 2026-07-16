---
description: Set your goals and check whether your real work is moving toward them
argument-hint: [check | add | list | done <id>]
---

# Goals

Goals turn the mentor from descriptive ("here's where you are") into directional
("here's where you're going — and are you actually heading there"). Each goal is
injected into every session so Claude nudges toward it, and the alignment check
scores your recent activity against what you said you wanted.

The CLI is `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py"`.

## Routing on `$ARGUMENTS`

- **`check` (or empty)** — run the alignment report (default action):
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" goal-check --days 14`
  Then render it plainly, leading with the headline number:
  - `alignment_pct` — what share of recent work advanced a stated goal. This is
    the "am I doing the right thing?" number. Interpret it, don't just print it:
    a low number isn't failure if priorities deliberately shifted — say so.
  - Per goal: verdict, and for skill goals the rating delta since it was set.
  - `top_off_goal_areas` — where the off-goal effort actually went. Name it; this
    is often the most useful line ("your stated goal is X but 60% went to Y").
  - End with one concrete suggestion: the goal with the best return on a little
    deliberate attention, grounded in the data.

- **`list`** — `goal-list`; summarise the active goals and their horizons.

- **`done <id>` / `pause <id>`** — `goal-status <id> done|paused`, confirm.

- **`add` (or a described goal)** — capture a new goal (see below).

## Adding a goal

Have a short exchange to make it concrete and measurable, then write it. A good
goal states the direction, and where possible links to concepts or areas so
progress can be tracked. Ask only what's missing:

- **text** — the goal itself, one sentence.
- **type** — `skill` (get better at something), `project` (ship something),
  `direction` (shift the balance of your work), or `habit` (change how you work,
  e.g. "stop letting the AI do all my TLS work").
- **concepts / areas** — link to concept ids from `stats` or areas (git, shell,
  unix, networking, containers, kubernetes, ci-cd, cloud, security, databases,
  web-backend, web-frontend, python, javascript, ai-llm, macos, editors, other)
  so the alignment check can measure it. Skill/direction goals should link
  something; pure project goals may not.
- **target** — optional rating (0–5) that marks the skill goal "achieved".
- **why / horizon** — optional motivation and target date.

Then pipe JSON to stdin:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" goal-add <<'EOF'
{"text": "Get genuinely fluent in Linux service management, not just able to run the commands",
 "type": "skill", "areas": ["unix"], "concepts": ["unix-process-management"],
 "target": 3.5, "why": "It's my most-repeated gap — the AI carries me every time",
 "horizon": "2026-09-01"}
EOF
```

Confirm what was saved, and note that the baseline rating is snapshotted now so
progress is measured from today forward — the first `check` mostly reflects your
recent past, and the delta becomes meaningful as you do new work.
