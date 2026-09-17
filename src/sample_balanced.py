#!/usr/bin/env python3
"""Step 6: build a reproducible BALANCED 150-review sample (50 per class) from the
entire Gift Cards dataset.

Ground truth (from rating, used ONLY for sampling + evaluation, never for model input):
    rating >= 4 -> POSITIVE
    rating == 3 -> NEUTRAL
    rating <= 2 -> NEGATIVE

Stratified random sample without replacement within each class, fixed seed 6418.
Preserves the original dataset row/index (1-based line number in the .jsonl.gz).

Outputs:
  results/step6_manifest.json   the exact sample (fully reproducible from the seed)
  also prints verification (150 total, 50 per class, no duplicate rows).
"""

from __future__ import annotations

import gzip
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "Gift_Cards.jsonl.gz"
OUT_MANIFEST = ROOT / "results" / "step6_manifest.json"

SEED = 6418
PER_CLASS = 50
EXPECTED_TOTAL = 150  # 50 x 3 classes


def ground_truth(rating) -> str:
    if not isinstance(rating, (int, float)):
        return "UNKNOWN"
    if rating >= 4:
        return "POSITIVE"
    if rating == 3:
        return "NEUTRAL"
    return "NEGATIVE"


def build_sample() -> list[dict]:
    buckets: dict[str, list[dict]] = {c: [] for c in ("POSITIVE", "NEUTRAL", "NEGATIVE")}
    with gzip.open(DATA_FILE, "rt", encoding="utf-8") as f:
        for row, line in enumerate(f, start=1):   # 1-based original dataset row
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rating = rec.get("rating")
            cls = ground_truth(rating)
            if cls == "UNKNOWN":
                continue
            buckets[cls].append({
                "row": row,
                "rating": rating,
                "ground_truth": cls,
                "title": (rec.get("title") or "").strip(),
                "text": (rec.get("text") or "").strip(),
                "asin": rec.get("asin"),
            })

    rng = random.Random(SEED)   # fixed seed -> reproducible sample
    sample = []
    for cls, items in buckets.items():
        if len(items) < PER_CLASS:
            raise SystemExit(f"Not enough {cls}: {len(items)} < {PER_CLASS}")
        sample.extend(rng.sample(items, PER_CLASS))   # without replacement, per class

    # Order the manifest by original row index for readability.
    sample.sort(key=lambda r: r["row"])
    return sample


def verify(sample) -> None:
    total = len(sample)
    counts = Counter(r["ground_truth"] for r in sample)
    rows = [r["row"] for r in sample]
    dup = len(rows) != len(set(rows))
    print("=== STEP 6 BALANCED SAMPLE VERIFICATION ===")
    print(f"total reviews       : {total}  (expected {EXPECTED_TOTAL})")
    print(f"actual class counts : POSITIVE={counts['POSITIVE']} NEUTRAL={counts['NEUTRAL']} "
          f"NEGATIVE={counts['NEGATIVE']}")
    print(f"duplicate rows      : {dup}")
    print(f"row range           : {min(rows)}..{max(rows)} over {max(rows)-min(rows)+1} original lines")
    assert total == 150, "must be 150"
    assert counts["POSITIVE"] == counts["NEUTRAL"] == counts["NEGATIVE"] == 50, "must be 50 each"
    assert not dup, "no duplicate rows"


def main() -> int:
    sample = build_sample()
    verify(sample)
    manifest = {
        "experiment": "Step 6 balanced three-class sample",
        "seed": SEED,
        "per_class": PER_CLASS,
        "total": len(sample),
        "ground_truth_rule": {"POSITIVE": "rating>=4", "NEUTRAL": "rating==3", "NEGATIVE": "rating<=2"},
        "sampling": "stratified, without replacement, fixed seed",
        "reviews": sample,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nmanifest saved: {OUT_MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
