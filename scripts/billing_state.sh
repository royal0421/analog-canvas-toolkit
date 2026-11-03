#!/usr/bin/env bash
# Print this cloud session's billing type in one word (e.g. ccr_promotional).
#
# Reads the newest `rate_limit_event` of this session through the
# claude-code-remote MCP endpoint listed in /tmp/mcp-config-<session>.json
# (the agent proxy adds the credentials).  No model call, so no tokens.
# When the newest page holds no such event the last value read is reused
# (/tmp/billing_state.last); `unknown` only if nothing was ever read.
#
#   bash scripts/billing_state.sh            -> ccr_promotional
#   bash scripts/billing_state.sh --resets   -> resetsAt of that event (epoch s)
#
# NB events only appear when the model calls the API, so a wait loop that
# makes no calls never sees a new one.  Wait on the clock instead:
#   until [ "$(date +%s)" -ge "$(bash scripts/billing_state.sh --resets)" ];
#   do sleep 300; done; date -u
#
# The session owner authorised this on 2026-11-03 (.claude/settings.json).
#
# ⚠️ DOES NOT WORK (tested 2026-11-03): the endpoint answers 401
# "authentication required" -- the agent proxy does not add credentials for
# it; Claude Code calls it with its own session credential, and lifting that
# credential into a shell script is not something this script will do.  It
# therefore prints `unknown` (or the last value it ever read).  Read the
# billing type with the claude-code-remote `list_events` tool instead.
set -u
mode=${1:-}
cfg=$(ls /tmp/mcp-config-cse_*.json 2>/dev/null | head -1)
last=/tmp/billing_state.last
if [ -z "$cfg" ]; then
    [ -s "$last" ] && sed -n "$([ "$mode" = --resets ] && echo 2 || echo 1)p" "$last" || echo unknown
    exit 0
fi
python3 - "$cfg" "$mode" "$last" <<'PY'
import json, os, re, subprocess, sys
cfg, mode, last = sys.argv[1], sys.argv[2], sys.argv[3]
srv = json.load(open(cfg))["mcpServers"]["claude-code-remote"]
sid = "session_" + re.search(r"cse_([A-Za-z0-9]+)", cfg).group(1)
url, hdr = srv["url"], srv.get("headers", {})
base = ["curl", "-sS", "-m", "30", "-D", "-", url,
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json, text/event-stream"]
for k, v in hdr.items():
    base += ["-H", "%s: %s" % (k, v)]

def call(body, session=None):
    args = list(base)
    if session:
        args += ["-H", "Mcp-Session-Id: " + session]
    out = subprocess.run(args + ["-d", json.dumps(body)], capture_output=True,
                         text=True, timeout=40).stdout
    head, _, payload = out.partition("\r\n\r\n")
    m = re.search(r"(?im)^mcp-session-id:\s*(\S+)", head)
    msgs = []
    for line in payload.splitlines():          # SSE or plain JSON
        line = line[5:].strip() if line.startswith("data:") else line.strip()
        if line.startswith("{"):
            try:
                msgs.append(json.loads(line))
            except ValueError:
                pass
    return (m.group(1) if m else session), msgs

try:
    s, _ = call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                            "clientInfo": {"name": "billing_state", "version": "1"}}})
    call({"jsonrpc": "2.0", "method": "notifications/initialized"}, s)
    _, msgs = call({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "list_events", "arguments": {
                        "session_id": sid, "kinds": ["rate_limit_event"],
                        "limit": 100}}}, s)
    text = json.dumps(msgs)
    kinds = re.findall(r'rateLimitType\\*"\s*:\s*\\*"([a-z_]+)', text)
    resets = re.findall(r'rateLimitType\\*"\s*:\s*\\*"[a-z_]+\\*"\s*,\s*'
                        r'\\*"resetsAt\\*"\s*:\s*(\d+)', text)
    if kinds:
        with open(last, "w") as f:
            f.write("%s\n%s\n" % (kinds[-1], resets[-1] if resets else 0))
except Exception:
    pass
try:
    kind, reset = open(last).read().split()[:2]
except (OSError, ValueError):
    kind, reset = "unknown", "0"
print(reset if mode == "--resets" else kind)
PY
