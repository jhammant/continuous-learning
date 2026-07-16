#!/usr/bin/env bash
# Turn queued session transcripts into learning events: digest each transcript,
# ask a cheap headless model call to extract signals about the USER, merge the
# result into the learner model. Safe to run any time; a lock guarantees a
# single instance. Failed sessions are retried up to MAX_ATTEMPTS, then dropped.
set -u

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
CLH="${CL_HOME:-$HOME/.continuous-learning}"
MODEL="${CL_EXTRACT_MODEL:-haiku}"
# Full command override, e.g. CL_EXTRACT_CMD="ollama run qwen2.5-coder:32b"
# for free, fully-local extraction. Must read the prompt on stdin and print
# the JSON response.
EXTRACT_CMD="${CL_EXTRACT_CMD:-claude -p --model $MODEL}"
MAX_ATTEMPTS=3

# Mark every child process (including headless claude and its hooks) so the
# plugin's own hooks no-op inside the extraction pipeline.
export CL_EXTRACT=1

[ "$(python3 "$SCRIPTS/cl.py" get-mode 2>/dev/null || echo active)" = "off" ] && exit 0

mkdir -p "$CLH/logs"
LOCK="$CLH/extract.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  # break a stale lock left by a crashed run (>1h old), else defer to the holder
  lock_age=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || stat -c %Y "$LOCK" 2>/dev/null || date +%s) ))
  [ "$lock_age" -gt 3600 ] && rmdir "$LOCK" 2>/dev/null
  mkdir "$LOCK" 2>/dev/null || exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

if [ -z "${CL_EXTRACT_CMD:-}" ]; then
  command -v claude >/dev/null 2>&1 || { echo "claude CLI not on PATH; skipping"; exit 0; }
fi

# wall-clock cap on the headless call where a timeout binary exists
TIMEOUT_CMD=""
if command -v timeout >/dev/null 2>&1; then TIMEOUT_CMD="timeout 240"
elif command -v gtimeout >/dev/null 2>&1; then TIMEOUT_CMD="gtimeout 240"; fi

give_up_or_retry() { # $1 = session id, $2 = reason
  n="$(python3 "$SCRIPTS/cl.py" attempt "$1")"
  if [ "$n" -ge "$MAX_ATTEMPTS" ]; then
    python3 "$SCRIPTS/cl.py" queue-done "$1"
    echo "$(date '+%F %T') giving up on $1 after $n attempts ($2)"
  else
    echo "$(date '+%F %T') $2 for $1 (attempt $n/$MAX_ATTEMPTS, will retry)"
  fi
}

python3 "$SCRIPTS/cl.py" queue-pending | while IFS=$'\t' read -r sid tpath; do
  [ -n "$sid" ] || continue

  if [ ! -f "$tpath" ]; then
    python3 "$SCRIPTS/cl.py" queue-done "$sid"
    continue
  fi

  digest="$(python3 "$SCRIPTS/cl.py" digest-transcript "$tpath")"
  rc=$?
  if [ $rc -ne 0 ]; then
    give_up_or_retry "$sid" "digest failed (exit $rc)"
    continue
  fi
  if [ -z "$digest" ]; then
    # genuinely too small to carry signal
    python3 "$SCRIPTS/cl.py" queue-done "$sid"
    continue
  fi

  # stamp events with when the session actually happened, not when we extract
  epoch="$(stat -f %m "$tpath" 2>/dev/null || stat -c %Y "$tpath" 2>/dev/null || echo '')"
  ts=""
  if [ -n "$epoch" ]; then
    ts="$(date -u -r "$epoch" +%Y-%m-%dT%H:%M:%S+00:00 2>/dev/null ||
          date -u -d "@$epoch" +%Y-%m-%dT%H:%M:%S+00:00 2>/dev/null || echo '')"
  fi

  out="$({ cat "$SCRIPTS/../prompts/extract-events.md"
           printf '\n\nTRANSCRIPT DIGEST:\n%s\n' "$digest"
         } | $TIMEOUT_CMD $EXTRACT_CMD 2>>"$CLH/logs/extract.log")"

  if [ -n "$out" ] &&
     printf '%s' "$out" | python3 "$SCRIPTS/cl.py" apply-events --session "$sid" \
       ${ts:+--ts "$ts"} >>"$CLH/logs/extract.log" 2>&1; then
    python3 "$SCRIPTS/cl.py" queue-done "$sid"
    echo "$(date '+%F %T') extracted $sid"
  else
    give_up_or_retry "$sid" "extraction failed"
  fi
done

exit 0
