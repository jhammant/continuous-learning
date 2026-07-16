---
description: Create and track a learning path — a curated curriculum toward a goal
argument-hint: [progress | new <topic> | list | done <id>]
---

# Learning paths

A path is an ordered sequence of concepts with per-step targets — a curriculum
you deliberately walk, versus the reactive model that just tracks what you
happen to touch. The current step is injected into every session so the mentor
leans into it when relevant.

The CLI is `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py"`.

## Routing on `$ARGUMENTS`

- **`progress` (or empty)** — `path-progress`; render each active path as a
  checklist: steps met vs. remaining, the next step, and % complete. Lead with
  the next concrete step to work on.

- **`list`** — `path-list`; summarise active paths.

- **`done <id>` / `pause <id>`** — `path-status <id> done|paused`, confirm.

- **`new <topic>` (or a described curriculum)** — design a path:
  1. Propose an ordered sequence of 3–7 concepts from foundation to fluency for
     the topic, grounded where possible in concept ids the user already has
     (check `stats`). Each step gets a target rating (default 3.5) and a
     one-line "what mastery looks like" note. Show it and let the user adjust
     order/scope before saving.
  2. Save it:

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" path-add <<'EOF'
     {"title": "Linux service management",
      "steps": [
        {"concept": "process-fundamentals", "area": "unix", "target": 3.0, "note": "ps/kill/signals, what a PID is"},
        {"concept": "systemd-units", "area": "unix", "target": 3.5, "note": "write and read a .service unit"},
        {"concept": "journald-logs", "area": "unix", "target": 3.5, "note": "journalctl for a failing service"}
      ]}
     EOF
     ```
  3. Offer to generate a starter quiz for the first step (see
     `/continuous-learning:quiz`), and note that steps advance automatically as
     the underlying concept ratings cross their targets through real work,
     recall, or study.
