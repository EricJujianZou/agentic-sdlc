#!/bin/bash
for r in armA-2 armA-3 armB-2 armB-3; do
  n=$(ls ~/bench2/logs/run_evaluation/$r-local/bench2-$r/*/report.json 2>/dev/null | wc -l)
  echo "$r: $n/20"
done
docker ps --format '{{.Names}} ({{.Status}})'
