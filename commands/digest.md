---
description: Learning digest — what you touched, where you wobbled, one exercise
argument-hint: [days]
---

# Learning digest

Window: `$ARGUMENTS` days if given, else 7.

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" stats --days <N>`.
2. Render a short digest (prose + at most one small table):
   - Concepts touched this window, with current rating and direction of travel.
   - Wins: hands_on_completed, predicted_correctly, used_correctly events.
   - Wobbles: struggled, asked_basic_question, predicted_incorrectly events.
   - Recall cards due (suggest /continuous-learning:recall if any).
3. Design ONE ~10-minute exercise targeting the weakest recently-active concept,
   grounded in their actual work (reuse real filenames, repos, or commands from the
   notes in stats where possible). Offer two paths: do it now with you coaching, or
   save it for later as a recall card via
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" add-review --concept <id> --question "..." --hint "..."`.

Keep the whole digest under ~25 lines. It should feel like a coach's note, not a report.
