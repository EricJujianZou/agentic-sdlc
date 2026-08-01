#!/bin/bash
# usage: finalize_task.sh <rNNN> <instance_id> <started_at> <self_assessment>
set -e
R="$1"; IID="$2"; STARTED="$3"; ASSESS="$4"
WS=/home/user/agentic-sdlc/bench5/workspaces/task
OUT=/home/user/agentic-sdlc/bench5/results/armB/opus5/$R
mkdir -p "$OUT"
cd "$WS"
git add -A
git diff --cached > "$OUT/patch.diff"
FIN=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 - "$OUT/meta.json" "$IID" "$STARTED" "$FIN" "$ASSESS" <<'PY'
import json, sys
p, iid, st, fin, assess = sys.argv[1:6]
json.dump({"instance_id": iid, "model": "opus5", "started_at": st,
           "finished_at": fin, "self_assessment": assess},
          open(p, "w"), indent=2)
PY
echo "WROTE $OUT"
wc -l "$OUT/patch.diff"
