#!/bin/bash
# Stage rep 2+3 predictions into WSL and grade all four runs sequentially.
set -u
SRC="/mnt/c/Users/zouju/Coding Projects/agentic-sdlc/bench2/results"
cd ~/bench2
for r in armA-2 armA-3 armB-2 armB-3; do
  cp "$SRC/$r/predictions.json" ~/bench2/$r.json || exit 1
done
echo STAGED
for r in armA-2 armA-3 armB-2 armB-3; do
  ~/sbv/bin/python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Verified --split test \
    --predictions_path ~/bench2/$r.json --max_workers 2 \
    --run_id $r-local --cache_level env 2>&1 | tail -6
  echo "DONE_$r"
done
echo ALL_DONE
