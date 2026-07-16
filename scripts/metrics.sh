#!/usr/bin/env bash
# Snapshot outcome metrics into the learner model. Currently GitHub (stars,
# forks, per-repo traction) via the gh CLI; optionally repo traffic with
# --traffic (needs push access to the repos). Safe to run repeatedly — each
# run appends one timestamped snapshot, building a time series the goal-check
# and metric-report read.
#
# Usage: metrics.sh [--traffic] [--user <login>]
set -u

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
CL="python3 $SCRIPTS/cl.py"

TRAFFIC=0
USER_LOGIN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --traffic) TRAFFIC=1 ;;
    --user) shift; USER_LOGIN="$1" ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

command -v gh >/dev/null 2>&1 || { echo "gh CLI not found — install it or record metrics manually with 'cl.py metric-record'"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "gh not authenticated — run 'gh auth login'"; exit 1; }

# All repos owned by the authenticated user (or --user), as one JSON object per
# line, fed to the aggregator. --paginate stitches the pages.
if [ -n "$USER_LOGIN" ]; then endpoint="users/$USER_LOGIN/repos"; else endpoint="user/repos"; fi
gh api --paginate "$endpoint" -X GET -f per_page=100 -f type=owner \
  --jq '.[] | {name: .full_name, stars: .stargazers_count, forks: .forks_count, issues: .open_issues_count}' \
  | $CL metric-github

# Optional: 14-day view counts per repo with traction (best effort; needs push).
if [ "$TRAFFIC" -eq 1 ]; then
  gh api --paginate "$endpoint" -X GET -f per_page=100 -f type=owner \
    --jq '.[] | select(.stargazers_count > 0) | .full_name' 2>/dev/null |
  while IFS= read -r repo; do
    [ -n "$repo" ] || continue
    views="$(gh api "repos/$repo/traffic/views" --jq '.count' 2>/dev/null)"
    [ -n "$views" ] && $CL metric-record "github.views14d.$repo" "$views" >/dev/null 2>&1
  done
  echo "traffic snapshot recorded where accessible"
fi

$CL metric-report --days 30 | python3 -c "
import json, sys
d = json.load(sys.stdin)
star_keys = [k for k in d['metrics'] if k.startswith('github.stars.') and k != 'github.stars.total']
tot = d['metrics'].get('github.stars.total', {})
print(f\"total stars: {tot.get('current')} ({tot.get('change_30d', 0) or 0:+g} /30d) across {len(star_keys)} repos with stars\")
"
