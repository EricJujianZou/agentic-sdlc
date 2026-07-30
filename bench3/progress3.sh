#!/bin/bash
for r in armA-1 armB-1 armA-2 armB-2 armA-3 armB-3; do
  d=~/bench3/logs/run_evaluation/b3-$r-local/bench3-$r
  [ -d "$d" ] && echo "$r: $(ls "$d"/*/report.json 2>/dev/null | wc -l)/20"
done
pgrep -f '[s]webench.harness' >/dev/null && echo RUNNING || echo NOT-RUNNING
docker ps --format '{{.Names}}'
