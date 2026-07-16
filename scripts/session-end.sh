#!/usr/bin/env bash
# SessionEnd hook: kick off background extraction of queued transcripts into
# learning events. Never blocks session teardown.
set -u

# Guard against recursion: the extraction pipeline runs headless claude
# sessions whose own SessionEnd would otherwise re-trigger this.
[ -n "${CL_EXTRACT:-}" ] && exit 0

cat > /dev/null # drain hook stdin

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLH="${CL_HOME:-$HOME/.continuous-learning}"

MODE="$(python3 "$ROOT/scripts/cl.py" get-mode 2>/dev/null || echo active)"
[ "$MODE" = "off" ] && exit 0

mkdir -p "$CLH/logs"
nohup "$ROOT/scripts/extract-events.sh" >> "$CLH/logs/extract.log" 2>&1 &

# Opportunistic outcome-metrics snapshot, throttled to ~once/day so the GitHub
# time series builds itself without hammering the API.
if command -v gh >/dev/null 2>&1; then
  stale="$(python3 - "$CLH" <<'PY'
import datetime, json, os, sys
p = os.path.join(sys.argv[1], "metrics.json")
try:
    h = json.load(open(p)).get("github.stars.total", {}).get("history", [])
    last = h[-1]["ts"] if h else None
except Exception:
    last = None
if not last:
    print("1")
else:
    age = (datetime.datetime.now(datetime.timezone.utc)
           - datetime.datetime.fromisoformat(last)).total_seconds()
    print("1" if age > 72000 else "0")  # 20 hours
PY
)"
  [ "$stale" = "1" ] && nohup "$ROOT/scripts/metrics.sh" >> "$CLH/logs/metrics.log" 2>&1 &
fi
exit 0
