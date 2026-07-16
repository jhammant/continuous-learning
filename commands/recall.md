---
description: Spaced-repetition quiz built from your own recent work
---

# Recall session

The CLI is `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py"`.

1. Process any un-extracted sessions first: run
   `"${CLAUDE_PLUGIN_ROOT}/scripts/extract-events.sh"`. It exits immediately if
   another extraction holds the lock; if there is a backlog it may take ~30s per
   session — tell the user if so.
2. Get due cards: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" due`
3. If nothing is due, say so, mention `next_due`, and stop.
4. Quiz ONE card at a time, at most 7:
   - Ask the question in your own words, grounded in where it came from ("last week
     you fixed that CORS error — …").
   - Wait for their answer before revealing anything. The hint is for nudging, not
     for reading out.
   - Grade honestly — being generous corrupts their learner model:
     `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" grade <id> <correct|partial|incorrect>`
   - After a miss, give a one-paragraph explanation at most, then move on.
   - Keep it warm and brief. No lecturing between cards.
5. Finish with a two-line summary: score, any notable rating changes, when the next
   cards come due. The user can stop at any point — grade what was answered and skip
   the rest.
