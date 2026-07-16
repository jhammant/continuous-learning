---
description: Open the live learning dashboard + in-browser recall in your browser
argument-hint: [stop | port]
---

# Dashboard

Starts the local dashboard (the live journey page + an in-browser recall quiz) as
a background process and opens it in your browser. Localhost only, no auth.

The CLI is `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py"`.

## Routing on `$ARGUMENTS`

- **`stop`** — shut it down:
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" serve --stop`, confirm.

- **a number** — use it as the port (default 8787).

- **otherwise (start)**:
  1. Pick the port (`$ARGUMENTS` if numeric, else 8787). Its URL is
     `http://127.0.0.1:<port>/`.
  2. If it's already up, just reopen it — check with
     `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:<port>/api/due`.
     A `200` means it's running; open the URL and stop.
  3. Otherwise start it **detached** so it outlives this turn, and open the browser:

     ```bash
     nohup python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cl.py" serve --port <port> \
       >> "${CL_HOME:-$HOME/.continuous-learning}/logs/serve.log" 2>&1 &
     disown
     sleep 1 && open "http://127.0.0.1:<port>/" 2>/dev/null || true
     ```
     (`serve` is idempotent — if the port is taken it just prints the existing
     URL and exits, so re-running is safe.)
  4. Tell the user the dashboard URL and the recall URL (`…/recall`), that it's
     local-only, and that `/continuous-learning:dashboard stop` shuts it down.

It keeps running in the background until stopped or you reboot. If you'd rather
have it always-on and self-restarting, it can be registered as a managed job —
mention that as an option, don't set it up unless asked.
