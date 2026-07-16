#!/usr/bin/env bash
# Backfill the learner model from historical Claude Code session transcripts.
# Enqueues them oldest-first (ratings are path-dependent: first evidence weighs
# double, so chronological order gives a sensible evolution), then runs the
# extractor. Already-processed sessions are skipped via the queue ledgers.
#
# Usage: backfill.sh [limit]     (default: all)
set -u

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
CLH="${CL_HOME:-$HOME/.continuous-learning}"
PROJECTS="${CL_PROJECTS_DIR:-$HOME/.claude/projects}"
LIMIT="${1:-100000}"

mkdir -p "$CLH/logs"
now="$(date +%s)"
queued=0
skipped=0

while IFS='|' read -r mtime tpath; do
  [ "$queued" -ge "$LIMIT" ] && break
  # skip transcripts touched in the last hour — likely a live session
  [ $((now - mtime)) -lt 3600 ] && continue
  sid="$(basename "$tpath" .jsonl)"
  if python3 "$SCRIPTS/cl.py" queue-add "$sid" "$tpath" >/dev/null 2>&1; then
    queued=$((queued + 1))
  else
    skipped=$((skipped + 1))
  fi
done < <(
  find "$PROJECTS" -maxdepth 2 -name "*.jsonl" -size +4k ! -path "*subagents*" 2>/dev/null |
  while IFS= read -r f; do
    printf '%s|%s\n' "$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f")" "$f"
  done | sort -n
)

echo "backfill: queued $queued sessions ($skipped already processed or queued)"
[ "$queued" -eq 0 ] && exit 0

echo "backfill: starting extraction (watch $CLH/logs/extract.log)"
"$SCRIPTS/extract-events.sh"
echo "backfill: done"
python3 "$SCRIPTS/cl.py" stats --days 90 | head -8
