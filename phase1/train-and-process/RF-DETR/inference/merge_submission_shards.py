"""Merge sharded predict_test_sahi.py outputs back into sample_submission.csv order and validate coverage.

Usage: python merge_submission_shards.py --out submissions/final.csv submissions/part0.csv submissions/part1.csv ...
"""
import argparse
import csv
from pathlib import Path

COMP = Path("/home/ubuntu/.cache/kagglehub/competitions/level-up-ai-roketsan-yapay-zeka-hackathonu")

parser = argparse.ArgumentParser()
parser.add_argument("parts", nargs="+")
parser.add_argument("--out", required=True)
parser.add_argument("--sample", default=str(COMP / "sample_submission.csv"))
args = parser.parse_args()

rows = {}
for part in args.parts:
    for row in csv.DictReader(open(part)):
        assert row["image_id"] not in rows, f"duplicate {row['image_id']}"
        rows[row["image_id"]] = row["PredictionString"]
order = [row["image_id"] for row in csv.DictReader(open(args.sample))]
missing = [i for i in order if i not in rows]
extra = set(rows) - set(order)
assert not missing and not extra, f"missing={missing[:5]} extra={list(extra)[:5]}"

with open(args.out, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["image_id", "PredictionString"])
    for image_id in order:
        writer.writerow([image_id, rows[image_id]])
n_boxes = sum(len(s.split()) // 6 for s in rows.values() if s != "none")
print(f"wrote {args.out}: {len(order)} images, {n_boxes} boxes, {sum(s == 'none' for s in rows.values())} 'none'")
