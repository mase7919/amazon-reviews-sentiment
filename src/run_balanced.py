#!/usr/bin/env python3
"""Step 6: run the balanced three-class LLM experiment over the 150 review sample.

Reads the sample from results/step6_manifest.json (seed 6418, 50/50/50), classifies
each review's title+body with the three-class prompt (prompts/sentiment_emotion_3class.txt),
and evaluates predicted sentiment against the rating-derived ground truth.

The model request contains ONLY title + body. rating / ground-truth class are
attached to the saved record only AFTER classification and never sent.

Outputs (results/):
  step6_llm.jsonl            incremental per-review record (resumable)
  step6_llm_metadata.json    non-secret run metadata
  step6_metrics.json         accuracy, 3x3 matrix, per-class recall/precision,
                             macro recall (balanced accuracy), mismatches, NEUTRAL split
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import classify

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
MANIFEST = RESULTS / "step6_manifest.json"
RAW_JSONL = RESULTS / "step6_llm.jsonl"
META_JSON = RESULTS / "step6_llm_metadata.json"
METRICS_JSON = RESULTS / "step6_metrics.json"

THREE = ("POSITIVE", "NEUTRAL", "NEGATIVE")
TEMPERATURE = 0.0
MAX_TRANSIENT_RETRIES = 3
RETRY_BACKOFF_S = 2.0


def prompt_sha256() -> str:
    return hashlib.sha256(
        classify.load_prompt(classify.THREE_CLASS_PROMPT_PATH).encode("utf-8")).hexdigest()


def classify_with_retry(title, body, client, model, row):
    last_err = None
    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        try:
            parsed, raw, _ = classify.classify_sentiment_emotion3(
                title, body, client=client, model=model, review_id=f"row{row}")
            return parsed, raw, None
        except classify.InvalidModelLabelError as exc:
            return None, None, f"malformed response: {exc}"
        except Exception as exc:
            last_err = exc
            if attempt < MAX_TRANSIENT_RETRIES:
                time.sleep(RETRY_BACKOFF_S * (attempt + 1))
    return None, "", f"api error: {last_err}"


def evaluate(rows):
    total = len(rows)
    # 3x3 confusion: rows=actual, cols=predicted (only valid predictions in matrix)
    mat = {a: {p: 0 for p in THREE} for a in THREE}
    failed = 0
    for r in rows:
        p = r["predicted"]
        if p in THREE:
            mat[r["ground_truth"]][p] += 1
        else:
            failed += 1

    correct = sum(mat[c][c] for c in THREE)
    # recall (row-normalized) and precision (col-normalized) per class
    rec, prec = {}, {}
    for c in THREE:
        rowsum = sum(mat[c][p] for p in THREE)
        colsum = sum(mat[a][c] for a in THREE)
        rec[c] = round(100.0 * mat[c][c] / rowsum, 2) if rowsum else float("nan")
        prec[c] = round(100.0 * mat[c][c] / colsum, 2) if colsum else float("nan")
    macro_recall = round(sum(v for v in rec.values() if v == v) / len(rec), 2)
    mismatches = [r for r in rows if r["predicted"] is not None
                  and r["predicted"] != r["ground_truth"]]

    # NEUTRAL distribution (how the actual NEUTRAL were classified)
    neutral_rows = [r for r in rows if r["ground_truth"] == "NEUTRAL"]
    neutral_split = {p: sum(1 for r in neutral_rows if r["predicted"] == p) for p in THREE}
    neutral_none = sum(1 for r in neutral_rows if r["predicted"] not in THREE)

    # confusion direction counts (actual -> predicted), valid predictions only
    direction = {}
    for a in THREE:
        for p in THREE:
            if a == p:
                continue
            direction[f"{a}->{p}"] = mat[a][p]

    return {
        "total": total,
        "failed_calls": failed,
        "overall_accuracy_pct": round(100.0 * correct / total, 2),
        "total_correct": correct,
        "total_incorrect": total - correct,
        "macro_recall_pct": macro_recall,
        "confusion_matrix_rows_actual_cols_predicted": mat,
        "class_recall_pct": rec,
        "class_precision_pct": prec,
        "neutral_distribution": neutral_split,
        "neutral_failed": neutral_none,
        "confusion_directions": direction,
        "mismatches": [{"row": m["row"], "title": m["title"],
                        "text": m["text"], "rating": m["rating"],
                        "ground_truth": m["ground_truth"], "predicted": m["predicted"]}
                       for m in mismatches],
        "validation": {
            "matrix_total": sum(sum(row.values()) for row in mat.values()),
            "per_class_actual_totals": {c: sum(mat[c][p] for p in THREE) for c in THREE},
        },
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reviews = manifest["reviews"]
    cfg = classify.read_api_env()
    client = classify.make_client(cfg)

    META_JSON.write_text(json.dumps({
        "experiment": "Step 6 balanced three-class LLM (150 reviews)",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": cfg["model"], "api_base_url": cfg["base"],
        "temperature": TEMPERATURE, "num_reviews": len(reviews),
        "sample_file": "results/step6_manifest.json", "sample_seed": manifest["seed"],
        "prompt_file": "prompts/sentiment_emotion_3class.txt", "prompt_sha256": prompt_sha256(),
        "input_fields_sent_to_model": ["title", "text"],
        "rating_or_ground_truth_sent_to_model": False,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    done = {}
    if RAW_JSONL.exists():
        for line in RAW_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["row"]] = r

    print(f"Scoring {len(reviews)} balanced reviews (3-class prompt, {cfg['model']})...")
    for k, rec in enumerate(reviews, start=1):
        row = rec["row"]
        if row in done:
            continue
        if k % 25 == 0:
            print(f"  ...processed {min(len(done), k)}/{len(reviews)}", flush=True)
        title, text = rec["title"], rec["text"]
        parsed, raw, error = classify_with_retry(title, text, client, cfg["model"], row=row)
        record = {
            "row": row,                 # original dataset row/index
            "title": title, "text": text,
            "rating": rec["rating"],    # ground truth for EVALUATION only, never sent
            "ground_truth": rec["ground_truth"],
            "predicted": (parsed or {}).get("sentiment"),
            "llm_emotion": (parsed or {}).get("emotion"),
            "raw_response": raw,
            "error": error,
        }
        record["matched"] = (record["predicted"] == record["ground_truth"]) \
            if record["predicted"] is not None else None
        done[row] = record
        with open(RAW_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        time.sleep(0.05)

    rows = [done[r["row"]] for r in reviews]
    failed = [r for r in rows if r["error"] is not None]
    if failed:
        print("FAILED rows:")
        for fr in failed:
            print(f"  row {fr['row']}: {fr['error']}")

    metrics = evaluate(rows)
    METRICS_JSON.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== STEP 6 THREE-CLASS METRICS ===")
    print(f"total              : {metrics['total']}")
    print(f"overall accuracy   : {metrics['overall_accuracy_pct']}%  "
          f"({metrics['total_correct']}/{metrics['total']} correct, "
          f"{metrics['total_incorrect']} incorrect)")
    print(f"macro recall (bal. acc.): {metrics['macro_recall_pct']}%")
    print("\nConfusion matrix (rows=actual, cols=predicted, POS/NEU/NEG):")
    print(f"  actual \\ pred   POSITIVE  NEUTRAL  NEGATIVE")
    for a in THREE:
        print(f"  {a:<12} " + "  ".join(f"{metrics['confusion_matrix_rows_actual_cols_predicted'][a][p]:>6}" for p in THREE))
    print("\nPer-class recall / precision:")
    for c in THREE:
        print(f"  {c:<9} recall={metrics['class_recall_pct'][c]}%  precision={metrics['class_precision_pct'][c]}%")
    print("\nNEUTRAL (actual=50) classified as:")
    for p in THREE:
        print(f"  -> {p}: {metrics['neutral_distribution'][p]}")
    print("\nConfusion directions:")
    for k, v in metrics["confusion_directions"].items():
        if v:
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
