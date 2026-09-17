#!/usr/bin/env python3
"""Step 5A: run the combined sentiment+emotion LLM over the SAME first 100 review
records, using the versioned Step 5 prompt (prompts/sentiment_emotion_prompt.txt).

Sends ONLY title + body to the model. The star rating, expected sentiment, the
original Step 2 prediction, and any NRC result are never sent.

Original Step 2 results (results/step2_raw_100.jsonl) are left untouched. The
sentiment returned by THIS new prompt is compared to the original Step 2
prediction and the differences are REPORTED (results/step5_llm_sentiment_compare.json),
never written back into the Step 2 file.

Outputs:
  results/step5_llm.jsonl                    one audit record per review
  results/step5_llm_metadata.json            non-secret run metadata
  results/step5_llm_sentiment_compare.json   sentiment diffs vs Step 2
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
from score_100 import first_n_records  # reuses the identical first-100 selection

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
RAW_JSONL = RESULTS_DIR / "step5_llm.jsonl"
META_JSON = RESULTS_DIR / "step5_llm_metadata.json"
COMPARE_JSON = RESULTS_DIR / "step5_llm_sentiment_compare.json"
STEP2_JSONL = RESULTS_DIR / "step2_raw_100.jsonl"

NUM_REVIEWS = 100
TEMPERATURE = 0.0
MAX_TRANSIENT_RETRIES = 3
RETRY_BACKOFF_S = 2.0


def prompt_sha256() -> str:
    return hashlib.sha256(
        classify.load_prompt(classify.EMOTION_PROMPT_PATH).encode("utf-8")).hexdigest()


def classify_with_retry(title: str, body: str, client, model: str, row: int):
    last_err = None
    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        try:
            parsed, raw, _ = classify.classify_sentiment_emotion(
                title, body, client=client, model=model, review_id=f"row{row}")
            return parsed, raw, None
        except classify.InvalidModelLabelError as exc:
            return None, None, f"malformed response: {exc}"
        except Exception as exc:
            last_err = exc
            if attempt < MAX_TRANSIENT_RETRIES:
                time.sleep(RETRY_BACKOFF_S * (attempt + 1))
    return None, "", f"api error: {last_err}"


def load_step2():
    out = {}
    if STEP2_JSONL.exists():
        for line in STEP2_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["row"]] = r
    return out


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = classify.read_api_env()
    client = classify.make_client(cfg)
    records = first_n_records(NUM_REVIEWS)

    metadata = {
        "experiment": "Step 5A combined sentiment+emotion LLM (first 100 records)",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": cfg["model"],
        "api_base_url": cfg["base"],
        "temperature": TEMPERATURE,
        "num_reviews": NUM_REVIEWS,
        "selection": "first 100 records in original file order",
        "prompt_file": "prompts/sentiment_emotion_prompt.txt",
        "prompt_sha256": prompt_sha256(),
        "emotions": list(classify.EMOTIONS),
        "input_fields_sent_to_model": ["title", "text"],
        "rating_or_prior_labels_sent_to_model": False,
    }
    META_JSON.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    done = {}
    if RAW_JSONL.exists():
        for line in RAW_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["row"]] = r

    print(f"Scoring {NUM_REVIEWS} reviews with combined sentiment+emotion prompt "
          f"({cfg['model']})...")
    for i, rec in enumerate(records, start=1):
        if i in done:
            continue
        if i % 25 == 0:
            print(f"  ...processed {min(len(done), i)}/{NUM_REVIEWS}", flush=True)
        title = (rec.get("title") or "").strip()
        text = (rec.get("text") or "").strip()
        rating = rec.get("rating")

        parsed, raw, error = classify_with_retry(title, text, client, cfg["model"], row=i)
        result = {
            "row": i,
            "rating": rating,               # ground truth ONLY, never sent
            "title": title,
            "text": text,
            "sentiment": (parsed or {}).get("sentiment"),
            "emotion": (parsed or {}).get("emotion"),
            "raw_response": raw,
            "error": error,
        }
        done[i] = result
        with open(RAW_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")
        time.sleep(0.05)

    rows = [done[i] for i in range(1, NUM_REVIEWS + 1)]
    step2 = load_step2()

    # --- Sentiment comparison vs original Step 2 (report only, no overwrite). ---
    compare = {"baseline_prompt": "prompts/sentiment_prompt.txt",
               "combined_prompt": "prompts/sentiment_emotion_prompt.txt",
               "note": "Combined-prompt sentiment vs original Step 2 prediction. "
                       "Original values are NOT modified."}
    diffs = []
    changed = unchanged = no_step2 = failed = 0
    for r in rows:
        orig = step2.get(r["row"])
        if orig is None:
            no_step2 += 1
            continue
        o_pred = orig.get("prediction")
        if o_pred is None or r["error"] is not None:
            if r["error"] is not None:
                failed += 1
            continue
        if r["sentiment"] == o_pred:
            unchanged += 1
        else:
            changed += 1
            diffs.append({"row": r["row"], "title": r["title"],
                          "step2_prediction": o_pred, "combined_sentiment": r["sentiment"]})
    compare.update({
        "total_compared": changed + unchanged + failed,
        "sentiment_changed": changed,
        "sentiment_unchanged": unchanged,
        "failed_calls": failed,
        "rows_without_step2": no_step2,
        "differences": diffs,
    })
    COMPARE_JSON.write_text(json.dumps(compare, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- Console report. ---
    failed_rows = [r for r in rows if r["error"] is not None]
    print("\n=== STEP 5A LLM EMOTION RUN ===")
    print(f"reviews processed: {len(rows)}")
    print(f"failed/malformed : {len(failed_rows)}")
    if failed_rows:
        for fr in failed_rows:
            print(f"  row {fr['row']}: {fr['error']}")
    from collections import Counter
    emo = Counter(r["emotion"] for r in rows if r["emotion"] is not None)
    print("LLM emotion distribution:")
    for e in classify.EMOTIONS:
        print(f"  {e:<13} {emo.get(e,0)}")
    print(f"\nSentiment comparison vs Step 2 baseline:")
    print(f"  changed   : {changed}")
    print(f"  unchanged : {unchanged}")
    print(f"  failed    : {failed}")
    if diffs:
        print("  differences (combined vs step2):")
        for d in diffs:
            print(f"    row {d['row']:>3}: step2={d['step2_prediction']:<8} combined={d['combined_sentiment']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
