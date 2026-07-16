---
description: View or calibrate your learner profile (levels, goals, mentor mode)
---

# Learner profile

Data lives under `~/.continuous-learning/` (or `$CL_HOME`). The CLI is
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py"`.

First run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" stats --days 30` and read
`"${CL_HOME:-$HOME/.continuous-learning}/profile.md"` if it exists.

## If not calibrated (stats shows "calibrated": false, or profile.md missing)

Run the calibration interview — conversational, ~1 minute, never a quiz:

1. Ask about (AskUserQuestion works well, one round, max 4 questions):
   - Their role and rough years of experience.
   - Areas they consider themselves strong in.
   - Areas they actively want to improve.
   - Preferred mentor mode: **quiet** (observe only), **active** (short calibrated
     asides + up to 2 optional checks per session), or **coach** (active + occasionally
     leaves small safe pieces of tasks for them, with hints).
2. Write `"${CL_HOME:-$HOME/.continuous-learning}/profile.md"`: a short narrative —
   who they are, goals, strong/weak areas, anything that should shape explanations
   (e.g. "deep Python, new to Docker").
3. Seed the concept model. Map what they told you to 8–15 kebab-case concepts with
   honest starting ratings: strong ≈ 4.0–4.5, wants-to-learn ≈ 1.5–2.0,
   mentioned-in-passing ≈ 2.5. Pipe JSON to stdin:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" seed <<'EOF'
   {"mode": "active",
    "concepts": {
      "docker-compose": {"rating": 1.5, "area": "containers", "name": "Docker Compose"},
      "python-asyncio": {"rating": 4.0, "area": "python", "name": "Python asyncio"}}}
   EOF
   ```

4. Confirm what was saved, and note that ratings self-correct from real evidence
   within a few sessions — the seed only needs to be roughly right. Calibration takes
   effect at the next session start.

## If calibrated

Summarize profile.md plus strongest/weakest concepts from stats, then ask whether
anything looks wrong. Disputes are evidence: fix ratings via `seed` (it merges into
the existing model) and update profile.md with anything new.
