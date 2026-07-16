---
description: Set the mentor mode — off, quiet, active, or coach
argument-hint: [off|quiet|active|coach]
---

# Mentor mode

The four modes:

- **off** — plugin dormant: no context injection, no observation, no extraction.
  Sessions run while off are never queued; sessions queued *before* switching off
  are held and only extracted after the mode is switched back on.
- **quiet** — observes and logs learning evidence, never interjects.
- **active** — calibrated one-sentence asides while working, plus up to 2 optional
  end-of-turn micro-checks per session (default).
- **coach** — active, plus occasionally leaves a small safe piece of a task for the
  user to do, with a hint.

If `$ARGUMENTS` contains one of those modes:
run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" set-mode <mode>`, confirm the
change in one sentence, and adopt the new behavior immediately yourself (the hook
injection catches up at next session start).

Otherwise: show the current mode
(`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" get-mode`) and the four options.
