#!/bin/bash
# usage: setup_task.sh <owner/repo> <base_commit>
set -e
SLUG="$1"; COMMIT="$2"
WS=/home/user/agentic-sdlc/bench5/workspaces/task
rm -rf "$WS"
mkdir -p "$WS"
cd "$WS"
git init -q .
git remote add origin "https://github.com/$SLUG.git"
if ! git fetch -q --depth 1 origin "$COMMIT" 2>/dev/null; then
  echo "shallow fetch of commit failed; doing full fetch"
  git fetch -q origin
fi
git checkout -q FETCH_HEAD 2>/dev/null || git checkout -q "$COMMIT"
echo "READY $SLUG @ $COMMIT"
git log --oneline -1
