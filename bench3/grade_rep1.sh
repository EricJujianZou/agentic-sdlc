#!/bin/bash
# Grade bench3 rep 1 (both arms) with clean docker config.
set -u
docker version --format '{{.Server.Version}}' || { echo NO_DOCKER; exit 1; }
mkdir -p ~/.docker-clean && echo '{}' > ~/.docker-clean/config.json
export DOCKER_CONFIG=~/.docker-clean
SRC="/mnt/c/Users/zouju/Coding Projects/agentic-sdlc/bench3/results"
mkdir -p ~/bench3 && cd ~/bench3
for r in armA-1 armB-1; do
  cp "$SRC/$r/predictions.json" ~/bench3/b3-$r.json || exit 1
done
echo STAGED
for r in armA-1 armB-1; do
  ~/sbv/bin/python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Verified --split test \
    --predictions_path ~/bench3/b3-$r.json --max_workers 2 \
    --run_id b3-$r-local --cache_level env 2>&1 | tail -6
  echo "DONE_$r"
done
echo ALL_DONE
