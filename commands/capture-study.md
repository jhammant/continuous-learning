---
description: Log what you've been learning outside Claude — from your activity history
argument-hint: [hours, default 24]
---

# Capture self-study

Most learning happens outside Claude Code — reading docs, watching talks, poking
at LM Studio. This pulls your recent activity from the **retrace** MCP and logs
it as `self_study` events, so those concepts show up in your learner model too
(distinct from `was_taught`, which is when Claude carried you).

**Opt-in and private by design:** it runs only when you invoke it, and it logs a
*concept id and a short topic note* — never full URLs, screenshots, or raw
history. Review before it writes if you like.

The CLI is `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py"`.

## Steps

1. Window = `$ARGUMENTS` hours if given, else 24. Compute the ISO start/end.
2. **Fine-grained first** (if this retrace setup captures screen content): call
   `retrace_timeline` (and/or `retrace_search` with `mode: "semantic"`) over the
   window, filtered to reading/browser apps. From the captions/snippets, identify
   distinct *learning topics* — docs, tutorials, Stack Overflow, technical
   videos, papers. Skip messaging, email, social, entertainment.
3. **Coarse fallback** (always available): call `retrace_stats` with
   `group_by: "app"` for the window. Map time in specialized learning apps to
   concepts — e.g. LM Studio / Ollama → `local-llm-inference`, Bambu Studio /
   OpenSCAD / Blender → `3d-printing-design`, Xcode / iPhone Simulator →
   `ios-app-distribution`. Ignore generic browsers here (no topic signal without
   captures) and anything under ~10 minutes.
4. Dedupe to one event per concept per run (not per capture). For each, log:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" log-event \
     --concept <kebab-id> --area <area> --type self_study \
     --note "<what you studied, one line — no URLs>"
   ```
   Use a concept id that already exists where possible (check `stats`); mint a
   clear new one otherwise.
5. Summarise what you logged: concept, rough time, topic. Note that `self_study`
   nudges the rating up modestly (you learned it yourself) and feeds the same
   trajectory and paths as everything else.

## Honest limitation

If `retrace_timeline` returns nothing, this setup only has **app-level** time, so
website- and video-level topics can't be recovered — you'll get coarse
per-app signals only. Fine-grained website capture needs retrace's screen-capture
source enabled, or a browser-side capture (a future `claude-in-chrome` path).
Say so rather than inventing specifics you can't see.
