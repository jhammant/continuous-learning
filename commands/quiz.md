---
description: Generate a targeted quiz on a topic, concept, or path step
argument-hint: <topic or concept or path-step>
---

# Quiz me

Generates focused questions on a topic and loads them as recall cards, so they
enter the same spaced-repetition schedule as your auto-extracted cards. Unlike
`/continuous-learning:recall` (which quizzes from what you already did), this
lets you deliberately drill something you want to get better at.

The CLI is `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py"`.

1. Resolve the target from `$ARGUMENTS` — a concept id, an area, a path step, or
   a free-text topic. If it maps to a known concept, use that id; otherwise pick
   a clear kebab-case concept id for it.
2. Write 4–6 questions pitched just above the user's current level on that
   concept (check `stats` for the rating — go easier if it's low, harder if
   high). Prefer questions that check *understanding* ("why does X happen when
   Y?") over trivia. Each needs a concept id, the question, and an optional hint.
3. Load them:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" review-bulk --source quiz <<'EOF'
   {"cards": [
     {"concept": "systemd-units", "question": "A service should restart on failure but not on clean exit — which directive, and what value?", "hint": "Restart="},
     {"concept": "systemd-units", "question": "What's the difference between `systemctl enable` and `systemctl start`?", "hint": "boot vs now"}
   ]}
   EOF
   ```
4. Offer to run them now (quiz the user through the just-added cards, grading
   with `cl.py grade <id> <correct|partial|incorrect>` as in
   `/continuous-learning:recall`) or leave them to surface on schedule.
