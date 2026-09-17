#!/usr/bin/env python3
"""Step 6 (NRC): word-list emotion scoring on the SAME 150-review balanced sample.

Reuses the Step 5 NRC implementation (emotion_nrc.py). Independent of rating,
ground truth, LLM sentiment, and LLM emotion -- its only inputs are title + body
plus the NRC lexicon.

Outputs:
  results/step6_nrc.jsonl        per-review scores + primary + tie/zero flags + audit
  results/step6_nrc_metadata.json
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import emotion_nrc as nrc_mod

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
MANIFEST = RESULTS / "step6_manifest.json"
OUT_JSONL = RESULTS / "step6_nrc.jsonl"
META_JSON = RESULTS / "step6_nrc_metadata.json"

EMOTIONS = nrc_mod.EMOTIONS


def main() -> int:
    lex = nrc_mod.load_lexicon(nrc_mod.LEXICON_PATH)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reviews = manifest["reviews"]

    RESULTS.mkdir(parents=True, exist_ok=True)
    OUT_JSONL.write_text("", encoding="utf-8")

    rows = []
    for rec in reviews:
        sc = nrc_mod.score_review(rec["title"], rec["text"], lex)
        row = {
            "row": rec["row"], "title": rec["title"], "text": rec["text"],
            "ground_truth": rec["ground_truth"], "rating": rec["rating"],
            "n_tokens": sc["n_tokens"],
            "scores": sc["scores"],
            "matched_words": sc["matched_words"],
            "primary": sc["primary"],
            "tie_resolved": sc["tie_resolved"],
            "zero_match": sc["zero_match"],
            "fallback_used": sc["fallback_used"],
        }
        rows.append(row)
        with open(OUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    metadata = {
        "experiment": "Step 6 NRC word-list emotion on balanced sample (150)",
        "lexicon": {
            "name": "NRC Emotion Lexicon (EmoLex) v0.92 word-level",
            "source": "https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm",
            "file": "lexicon/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt",
            "citation": "Mohammad & Turney (2013)",
        },
        "emotions": list(EMOTIONS),
        "same_rules_as_step5": True,
        "tokenization": "lowercase; split on runs of non-alphabetic characters",
        "scoring": "+1 per emotion per matched lexicon word (flag==1)",
        "primary_rule": "highest total count",
        "tie_rule": "first in canonical order among tied maxima",
        "zero_match_rule": "fallback primary = trust, fallback_used=True (reported)",
        "independent_of": ["rating", "ground_truth", "LLM sentiment", "LLM emotion"],
    }
    META_JSON.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    prim = Counter(r["primary"] for r in rows)
    ties = sum(1 for r in rows if r["tie_resolved"])
    zm = sum(1 for r in rows if r["zero_match"])
    print("=== STEP 6 NRC EMOTION (balanced 150) ===")
    print("primary emotion distribution:")
    for e in EMOTIONS:
        print(f"  {e:<13} {prim.get(e,0)}")
    print(f"tie_resolved    : {ties}")
    print(f"zero_match      : {zm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
