"""Build a one-instance gold-patch predictions file (grading-pipeline sanity check)."""
import json
import os
import urllib.parse
import urllib.request

IID = "django__django-17029"
q = urllib.parse.quote(f"\"instance_id\"='{IID}'")
url = ("https://datasets-server.huggingface.co/filter"
       "?dataset=princeton-nlp%2FSWE-bench_Verified&config=default&split=test"
       f"&where={q}")
with urllib.request.urlopen(url) as r:
    row = json.load(r)["rows"][0]["row"]
gold = row["patch"]
preds = {IID: {"model_patch": gold, "model_name_or_path": "gold-sanity"}}
os.makedirs("bench2/results/gold-sanity", exist_ok=True)
with open("bench2/results/gold-sanity/predictions.json", "w",
          encoding="utf-8", newline="\n") as f:
    json.dump(preds, f, indent=2)
print("gold patch bytes:", len(gold))
print(repr(gold[:200]))
