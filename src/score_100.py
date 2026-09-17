#!/usr/bin/env python3
"""Step 2: score the FIRST 100 review records (in file order) with the Step 1
binary sentiment classifier, and evaluate against the star-rating-derived
ground truth.

Ground truth is derived ONLY AFTER the model prediction for that review:
    rating >= 4  -> POSITIVE
    rating <  4  -> NEGATIVE
The model request always contains ONLY review title + body (plus the fixed
prompt). The rating / expected label are never sent to the model.

Resilience & reproducibility:
  - Results are appended line-by-line to results/step2_raw_100.jsonl, and the
    script resumes from already-scored rows if interrupted.
  - Every response is validated with classify.parse_label(). A malformed label
    is recorded as a failure (no label substituted). A genuine transient API
    error is retried a few times; if it still fails the row is recorded as an
    error, never silently given a label.
  - temperature is fixed at 0.0 for reproducibility.
  - Non-secret run metadata (model id, base URL, prompt hash, count, temperature)
    is written to results/step2_metadata.json. The API key is never written.

Usage:
    python src/score_100.py
Reads OPENAI_API_BASE / OPENAI_API_KEY / SENTIMENT_MODEL from env or the
git-ignored project .env (see src/classify.py).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import classify

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "Gift_Cards.jsonl.gz"
RESULTS_DIR = ROOT / "results"
RAW_JSONL = RESULTS_DIR / "step2_raw_100.jsonl"
META_JSON = RESULTS_DIR / "step2_metadata.json"
AGG_JSON = RESULTS_DIR / "step2_results.json"

NUM_REVIEWS = 100
TEMPERATURE = 0.0
MAX_TRANSIENT_RETRIES = 3
RETRY_BACKOFF_S = 2.0


def first_n_records(n: int) -> list[dict]:
    """Return the first `n` review records in original file order."""
    records = []
    with gzip.open(DATA_FILE, "rt", encoding="utf-8") as f:
        for line in f:              # iterate in file order
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
            if len(records) >= n:
                break
    if len(records) < n:
        raise SystemExit(f"Only {len(records)} records read; expected {n}.")
    return records


def prompt_sha256() -> str:
    return hashlib.sha256(classify.load_prompt().encode("utf-8")).hexdigest()


def derive_expected(rating) -> str:
    """Ground-truth binary label from rating (used ONLY after prediction)."""
    return "POSITIVE" if rating >= 4 else "NEGATIVE"


def classify_with_retry(title: str, body: str, client, model: str, row: int):
    """Classify one review; retry transient API errors, record failures cleanly.

    Returns (prediction|None, raw|None, error|None).
    """
    last_err = None
    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        try:
            label, raw, _ = classify.classify_sentiment(
                title, body, client=client, model=model, review_id=f"row{row}")
            return label, raw, None
        except classify.InvalidModelLabelError as exc:
            return None, None, f"malformed response: {exc}"
        except Exception as exc:  # transient/network/server error -> retry
            last_err = exc
            if attempt < MAX_TRANSIENT_RETRIES:
                time.sleep(RETRY_BACKOFF_S * (attempt + 1))
    # exhausted all retries for a transient error
    return None, "", f"api error: {last_err}"


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = classify.read_api_env()          # base + key + model (key never printed/saved)
    client = classify.make_client(cfg)
    records = first_n_records(NUM_REVIEWS)

    # --- Non-secret metadata (key deliberately omitted). ---
    metadata = {
        "experiment": "Step 2 binary sentiment scoring (first 100 records)",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": cfg["model"],
        "api_base_url": cfg["base"],
        "temperature": TEMPERATURE,
        "num_reviews": NUM_REVIEWS,
        "selection": "first 100 records in original file order (no balancing/randomization)",
        "ground_truth_rule": "rating>=4 -> POSITIVE; rating<4 -> NEGATIVE (derived after prediction)",
        "prompt_file": "prompts/sentiment_prompt.txt",
        "prompt_sha256": prompt_sha256(),
        "rating_not_sent_to_model": True,
    }
    META_JSON.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # --- Resume: rows already scored are keyed by their 1-based file line. ---
    done: dict[int, dict] = {}
    if RAW_JSONL.exists():
        for line in RAW_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["row"]] = r

    print(f"Scoring up to {NUM_REVIEWS} reviews against {cfg['model']}...")
    completed = 0
    for i, rec in enumerate(records, start=1):   # `row` = position in file (1-based)
        if i in done:
            completed += 1
            continue
        title = (rec.get("title") or "").strip()
        text = (rec.get("text") or "").strip()
        rating = rec.get("rating")

        if i % 25 == 0:
            print(f"  ...processed {min(len(done), i)}/{NUM_REVIEWS}", flush=True)

        prediction, raw, error = classify_with_retry(title, text, client, cfg["model"], row=i)
        # Ground truth derived AFTER the model was called for this review.
        expected = derive_expected(rating)
        matched = (prediction == expected) if prediction is not None else None

        result = {
            "row": i,                       # position in the dataset file (1-based)
            "rating": rating,
            "title": title,
            "text": text,
            "prediction": prediction,       # None if the call failed / malformed
            "expected": expected,
            "matched": matched,             # None on failure, True/False otherwise
            "raw_response": raw,
            "error": error,
        }
        done[i] = result
        # Append incrementally so an interruption loses at most this row.
        with open(RAW_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")
        completed += 1
        time.sleep(0.05)  # small pacing between calls

    # --- Aggregate metrics from the (possibly resumed) done dict. ---
    rows = [done[i] for i in range(1, NUM_REVIEWS + 1)]
    return compute_and_save_metrics(rows, metadata, AGG_JSON)


def compute_and_save_metrics(rows, metadata, agg_path: Path) -> int:
    total = len(rows)
    failures = [r for r in rows if r["prediction"] is None]
    valid = [r for r in rows if r["prediction"] is not None]

    def pct(n): return (100.0 * n / total) if total else 0.0

    actual_pos = sum(1 for r in rows if r["expected"] == "POSITIVE")
    actual_neg = total - actual_pos
    matched = sum(1 for r in rows if r["matched"] is True)
    accuracy = (100.0 * matched / total) if total else 0.0   # over all 100 incl. failures
    mismatches = [r for r in valid if r["matched"] is False]

    # Confusion matrix components over VALID predictions.
    tp = sum(1 for r in valid if r["expected"] == "POSITIVE" and r["prediction"] == "POSITIVE")
    fp = sum(1 for r in valid if r["expected"] == "NEGATIVE" and r["prediction"] == "POSITIVE")
    fn = sum(1 for r in valid if r["expected"] == "POSITIVE" and r["prediction"] == "NEGATIVE")
    tn = sum(1 for r in valid if r["expected"] == "NEGATIVE" and r["prediction"] == "NEGATIVE")

    # Class recall (per actual class) and precision (per predicted class).
    rec_pos = (100.0 * tp / (tp + fn)) if (tp + fn) else float("nan")
    rec_neg = (100.0 * tn / (tn + fp)) if (tn + fp) else float("nan")
    prec_pos = (100.0 * tp / (tp + fp)) if (tp + fp) else float("nan")
    prec_neg = (100.0 * tn / (tn + fn)) if (tn + fn) else float("nan")

    metrics = {
        "total_reviews": total,
        "actual_positive_count": actual_pos,
        "actual_positive_pct": round(pct(actual_pos), 2),
        "actual_negative_count": actual_neg,
        "actual_negative_pct": round(pct(actual_neg), 2),
        "overall_accuracy_pct": round(accuracy, 2),
        "matched_count": matched,
        "mismatch_count": len(mismatches),
        "failed_calls": len(failures),
        "confusion_matrix": {
            "axis_note": "rows=actual, columns=predicted",
            "actual_POS_pred_POS": tp,
            "actual_POS_pred_NEG": fn,   # FN
            "actual_NEG_pred_POS": fp,   # FP
            "actual_NEG_pred_NEG": tn,
        },
        "class_performance": {
            "POSITIVE_recall_pct": round(rec_pos, 2),
            "NEGATIVE_recall_pct": round(rec_neg, 2),
            "POSITIVE_precision_pct": round(prec_pos, 2),
            "NEGATIVE_precision_pct": round(prec_neg, 2),
        },
    }
    AGG_JSON.write_text(
        json.dumps({"metadata": metadata, "metrics": metrics,
                    "mismatches": [{"row": m["row"], "rating": m["rating"],
                                    "title": m["title"], "text": m["text"],
                                    "expected": m["expected"], "predicted": m["prediction"]}
                                   for m in mismatches],
                    "failures": [{"row": f["row"], "error": f["error"]} for f in failures]},
                   indent=2, ensure_ascii=False),
        encoding="utf-8")

    print("\n========== STEP 2 METRICS ==========")
    print(f"total reviews scored       : {total}")

    f_cnt = len(failures)
    print(f"valid predictions          : {len(valid)}", f"(failures: {f_cnt})" if f_cnt else "")
    print(f"actual POSITIVE            : {actual_pos} ({pct(actual_pos):.2f}%)")
    print(f"actual NEGATIVE            : {actual_neg} ({pct(actual_neg):.2f}%)")
    print(f"overall accuracy (agreement): {accuracy:.2f}%  ({matched}/{total})")
    print("\nConfusion matrix (rows=actual, cols=predicted):")
    print(f"                    predicted POSITIVE   predicted NEGATIVE")
    print(f"actual POSITIVE            {tp:>4}                {fn:>4}")
    print(f"actual NEGATIVE            {fp:>4}                {tn:>4}")
    print("\nClass-specific (valid predictions):")
    print(f"  POSITIVE recall: {rec_pos:.2f}%   precision: {prec_pos:.2f}%")
    print(f"  NEGATIVE recall: {rec_neg:.2f}%   precision: {prec_neg:.2f}%")
    print(f"total mismatches: {len(mismatches)}")
    if failures:
        print("\nFAILED/MALFORMED rows:", failures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
