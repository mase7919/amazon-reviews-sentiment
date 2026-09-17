#!/usr/bin/env python3
"""Step 1 spot-check: classify a handful of clearly positive and clearly negative
Amazon Gift Cards reviews with the binary sentiment prompt.

The star rating is used ONLY to (a) pick obvious examples and (b) verify predictions
afterwards. It is never sent to the model -- each call sends title + body only.

Run:
    python src/spot_check.py
Requires OPENAI_API_BASE, OPENAI_API_KEY, SENTIMENT_MODEL in the environment.

Artifacts written under results/:
    spotcheck_inputs.json   exactly what was sent to the model (title, body) -- auditable
    spotcheck_predictions.json  prediction + ground-truth rating per review
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

import classify

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "Gift_Cards.jsonl.gz"
RESULTS_DIR = ROOT / "results"

# Counts to select; obvious examples only.
N_POSITIVE = 4
N_NEGATIVE = 4
N_EMPTY = 1  # empty body, title present -- exercises an edge-case rule.

POS_KEYWORDS = {"great", "love", "perfect", "excellent", "awesome", "recommend", "best", "nice"}
NEG_KEYWORDS = {"terrible", "worst", "waste", "hate", "awful", "useless", "broken", "refund",
                "frustrated", "disappointed", "scam"}


def _has_any(text: str, keywords: set[str]) -> bool:
    words = set(text.lower().split())
    return bool(words & keywords)


def select_reviews():
    """Scan the dataset deterministically for obvious positive/negative/empty examples.

    Returns a list of dicts: {review_id, title, text, rating}. The rating is kept
    only as ground truth for the report -- it is never part of the model input.
    """
    positives, negatives, empties = [], [], []
    with gzip.open(DATA_FILE, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rating = rec.get("rating")
            text = (rec.get("text") or "").strip()
            title = (rec.get("title") or "").strip()

            item = {"review_id": rec.get("user_id", "?") + ":" + rec.get("asin", "?"),
                    "title": title, "text": text, "rating": rating}
            if not text and title and len(empties) < N_EMPTY and rating in (4.0, 5.0):
                empties.append(item); continue
            if rating in (4.0, 5.0) and _has_any(text, POS_KEYWORDS) and len(positives) < N_POSITIVE:
                positives.append(item); continue
            if rating in (1.0, 2.0) and _has_any(text, NEG_KEYWORDS) and len(negatives) < N_NEGATIVE:
                negatives.append(item); continue
            if (len(positives) >= N_POSITIVE and len(negatives) >= N_NEGATIVE
                    and len(empties) >= N_EMPTY):
                break

    all_reviews = positives + negatives + empties
    if not all_reviews:
        raise SystemExit("No obvious examples found -- check selection keywords/data.")
    return all_reviews


def main() -> int:
    reviews = select_reviews()

    # ---- Audit: exactly what will be sent to the model (no rating). ----
    inputs_payload = [
        {"review_id": r["review_id"], "title": r["title"], "text": r["text"]}
        for r in reviews
    ]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "spotcheck_inputs.json").write_text(
        json.dumps(inputs_payload, indent=2), encoding="utf-8")

    cfg = classify.read_api_env()
    client = classify.make_client(cfg)

    predictions = []
    print("Sending to the model for each review: Title + Text only (no rating).\n")
    for r in reviews:
        print(f"  classifying review {r['review_id']!r} ...", flush=True)
        label, raw, messages = classify.classify_sentiment(
            r["title"], r["text"], client=client, model=cfg["model"], review_id=r["review_id"])
        predictions.append({
            "review_id": r["review_id"],
            "title": r["title"],
            "text": r["text"],
            "predicted": label,
            "raw_response": raw,
            "rating_ground_truth": r["rating"],   # never sent to the model
        })
        print(f"    -> {label}\n")

    # ---- Save predictions + ground truth for later inspection. ----
    (RESULTS_DIR / "spotcheck_predictions.json").write_text(
        json.dumps(predictions, indent=2), encoding="utf-8")

    # ---- Report predictions first, ratings only AFTER all predictions are done. ----
    print("\n===== PREDICTIONS (from title + text only) =====")
    for p in predictions:
        body = (p["text"] or f"[EMPTY BODY; title used: {p['title']}]")
        snippet = (body[:90] + "…") if len(body) > 90 else body
        print(f"  [{p['predicted']:>8}] {snippet!r}")
        print(f"               title: {p['title']!r}")

    print("\n===== GROUND-TRUTH RATINGS (for verification AFTER predictions) =====")
    ok = 0
    for i, p in enumerate(predictions, start=1):
        gt = p["rating_ground_truth"]
        truth = "POSITIVE" if gt >= 4 else "NEGATIVE"
        correct = p["predicted"] == truth
        ok += int(correct)
        print(f"  #{i:<2} rating={gt} -> expected {truth:<8} model said {p['predicted']:<8} "
              f"{'OK' if correct else 'MISMATCH'}")

    print(f"\nAgreement: {ok}/{len(predictions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
