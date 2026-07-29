#!/bin/bash
# Classify error instances: infra (docker) vs patch-apply failures.
for pair in \
  "armA-2 pytest-dev__pytest-6197" \
  "armA-3 scikit-learn__scikit-learn-14629" \
  "armB-2 django__django-17029" \
  "armB-2 matplotlib__matplotlib-26113" \
  "armB-2 scikit-learn__scikit-learn-10908" \
  "armB-2 sphinx-doc__sphinx-9698" \
  "armB-2 sympy__sympy-19346" \
  "armB-3 matplotlib__matplotlib-26113" \
  "armB-3 mwaskom__seaborn-3187" \
  "armB-3 psf__requests-1766" \
  "armB-3 pytest-dev__pytest-5631" \
  "armB-3 scikit-learn__scikit-learn-10908" \
; do
  set -- $pair
  run=$1; iid=$2
  log=~/bench2/logs/run_evaluation/$run-local/bench2-$run/$iid/run_instance.log
  if [ -f "$log" ]; then
    reason=$(grep -oE "Credentials store error|Patch Apply Failed|APPLY_PATCH_FAIL|Error occurred while pulling image|error during connect|read: connection reset" "$log" | sort -u | tr '\n' ';')
    echo "$run/$iid: ${reason:-UNKNOWN-see-log}"
  else
    echo "$run/$iid: NO LOG"
  fi
done
