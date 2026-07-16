# Contributing

Thanks for looking at continuous-learning. It's a young project and the
interesting problems are wide open.

## Ground rules

- **Privacy is the product.** Nothing about a user's learning may leave their
  machine except the extraction call (which they can point at a local model).
  Don't add telemetry, don't phone home, don't commit anyone's data.
- **Teaching must never block work.** Every interaction the plugin adds to a
  Claude Code session must be skippable at zero cost. If it slows the real task
  down, it's a regression even if the pedagogy is good.
- **Keep it stdlib.** `cl.py` is deliberately dependency-free Python. New data-
  layer code should stay that way so `pip install` is never required.

## Layout

- `scripts/cl.py` — the whole data layer + CLI (concepts, events, goals, paths,
  metrics, recall, serve). Every subcommand is safe to run repeatedly.
- `scripts/*.sh` — the extraction / backfill / metrics pipelines.
- `scripts/journey.py` + `assets/journey-template.html` — the visual generator.
- `commands/`, `skills/`, `hooks/` — the Claude Code plugin surface.

## Dev loop

```bash
export CL_HOME=/tmp/cl-dev          # a throwaway learner model
python3 scripts/cl.py seed <<< '{"concepts":{"git-rebase":{"rating":2,"area":"git"}}}'
python3 scripts/cl.py stats
python3 scripts/cl.py serve --open  # dashboard + browser recall
claude plugin validate .            # before every PR
```

## High-value directions

- **Richer knowledge tracing** — the rating model is simple Elo-style nudges;
  Bayesian Knowledge Tracing or IRT would be more principled.
- **Web/reading capture** — turning what you study outside the terminal into
  `self_study` events (see `commands/capture-study.md`); browser-side capture is
  the obvious next source.
- **Multi-provider extraction** — the extractor already supports any
  `CL_EXTRACT_CMD`; first-class Ollama/LM-Studio presets would help.

Conventional-commit messages, focused PRs, and a passing `claude plugin validate`
are all that's asked.
