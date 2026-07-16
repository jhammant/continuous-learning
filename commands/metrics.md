---
description: Track real-world outcomes (GitHub stars, revenue, social) and tie them to goals
argument-hint: [pull | report | revenue <n> | record <key> <value>]
---

# Outcome metrics

The learner model measures your *activity and skill*. Metrics measure the
*results* — GitHub stars, revenue, social reach — so goals like "grow audience"
or "turn projects into revenue" get real numbers instead of activity proxies.
Each snapshot is timestamped, so the value of this grows over time as a trend.

The CLI is `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py"`.

## Routing on `$ARGUMENTS`

- **`pull` (or empty)** — snapshot GitHub now via `gh`:
  `"${CLAUDE_PLUGIN_ROOT}/scripts/metrics.sh"` (add `--traffic` for repo view
  counts where you have push access). Needs the `gh` CLI authenticated. Then
  report what changed.

- **`report`** — `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" metric-report --days 30`.
  Render each metric with its current value and change over the window; lead
  with total GitHub stars and any manually-tracked revenue/social. Call out the
  fastest-moving repo.

- **`revenue <n>`** — record revenue:
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" metric-record revenue.total <n>`.

- **`record <key> <value>`** — any custom numeric metric, e.g.
  `metric-record social.x.followers 1200`, `metric-record social.linkedin.followers 800`.
  Use dotted keys so related metrics group.

## What's automatic vs manual

- **GitHub** (stars, forks, per-repo, optional traffic) — automatic via
  `metrics.sh`. Run it periodically; it also runs opportunistically at session
  end. For a hands-off daily trend, schedule it: `/schedule` a cron that runs
  `metrics.sh`, or add a cron entry yourself.
- **Revenue and social** — manual (`metric-record`), since there's no universal
  API. Drop in a number whenever it changes; the trend builds from your entries.

## Tie a metric to a goal

Goals carry an optional `metrics` list of keys (edit `goals.json` or ask when
adding a goal). `/continuous-learning:goals check` then shows the current value
and its change since the goal was set, right next to the goal — so "grow
audience" reads as "276 stars (+14 since you set this)" rather than a vibe.
