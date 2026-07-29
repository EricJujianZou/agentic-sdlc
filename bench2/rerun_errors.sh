#!/bin/bash
# Re-run infra-error instances with a clean docker config (no credsStore).
set -u
docker version --format '{{.Server.Version}}' || { echo NO_DOCKER; exit 1; }
mkdir -p ~/.docker-clean
echo '{}' > ~/.docker-clean/config.json
export DOCKER_CONFIG=~/.docker-clean
cd ~/bench2
rerun() {
  run=$1; shift
  ~/sbv/bin/python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Verified --split test \
    --predictions_path ~/bench2/$run.json --instance_ids "$@" \
    --max_workers 1 --run_id $run-local --cache_level env 2>&1 | tail -4
  echo "RERUN_DONE_$run"
}
rerun armA-2 pytest-dev__pytest-6197
rerun armA-3 scikit-learn__scikit-learn-14629
rerun armB-2 django__django-17029 matplotlib__matplotlib-26113 scikit-learn__scikit-learn-10908 sphinx-doc__sphinx-9698 sympy__sympy-19346
rerun armB-3 matplotlib__matplotlib-26113 mwaskom__seaborn-3187 psf__requests-1766 pytest-dev__pytest-5631 scikit-learn__scikit-learn-10908
echo ALL_RERUNS_DONE
