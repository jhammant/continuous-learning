---
description: Render a visual learning-journey page from your local learner model
argument-hint: [output path]
---

# Learning journey

Generates a self-contained, shareable HTML page from your learner model:
skill trajectory (replayed chronologically), the taught→fluent shift, current
standing with growth edges flagged, signature skills, outcome metrics, and goals.
No personal data touches the repo — the page is built locally from
`~/.continuous-learning/`.

1. Run the generator (default output is `$CL_HOME/journey.html`):
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/journey.py" "$ARGUMENTS"`
   (if `$ARGUMENTS` is empty, omit it and use the default path).
2. Tell the user where it was written and the headline it reported (event count,
   fluency %, stars). Offer to open it in a browser.
3. If they want to share it, offer to publish it as an Artifact (the file is
   already self-contained). Point out it contains their real data, so it's theirs
   to share deliberately.

Needs at least a handful of logged events — if the model is empty, suggest
`scripts/backfill.sh` to seed from existing Claude Code history first.
