#!/usr/bin/env python3
"""Step 5B: NRC word-list primary emotion for the first 100 reviews.

Scores the review's title + body against the NRC Emotion Lexicon v0.92
(lexicon/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt) for the eight emotion classes,
then picks the highest-scoring emotion as the NRC primary emotion.

This method is completely independent of rating, LLM prediction, LLM emotion, and
expected sentiment: its ONLY inputs are the review title and body plus the lexicon.

Defined rules (documented for reproducibility):
  TOKENIZATION : lowercase, split on any run of non-alphabetic characters
                 (so "don't" -> ["don", "t"], "5-star" -> ["star"], "🎁" dropped).
  SCORING      : for each token present in the lexicon, +1 to each emotion that
                 word is associated with (word-level, flag==1). Sum per emotion.
  PRIMARY      : emotion with the highest total count.
  TIES         : among tied maxima, the FIRST emotion in the canonical order
                 [anger, anticipation, disgust, fear, joy, sadness, surprise, trust]
                 wins (deterministic; noted per review as tie_resolved=True).
  ZERO MATCH   : if no token matched any emotion, primary is set to the documented
                 fallback "trust" and fallback_used=True (the zero-match review is
                 reported, not hidden).

Outputs:
  results/step5_nrc.jsonl            per-review scores + primary + audit words
  results/step5_nrc_metadata.json    source/license + tokenization + tie/fallback rules
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from score_100 import first_n_records

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEXICON_PATH = PROJECT_ROOT / "lexicon" / "NRC-Emotion-Lexicon-Wordlevel-v0.92.txt"
RESULTS_DIR = PROJECT_ROOT / "results"
OUT_JSONL = RESULTS_DIR / "step5_nrc.jsonl"
META_JSON = RESULTS_DIR / "step5_nrc_metadata.json"

EMOTIONS = ("anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust")
FALLBACK_EMOTION = "trust"
NUM_REVIEWS = 100


def load_lexicon(path: Path) -> dict[str, set[str]]:
    """Return {word: set(emotions)} for words with association flag == 1."""
    lex: dict[str, set[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3 or parts[2] != "1":
            continue
        word, emotion = parts[0].strip().lower(), parts[1].strip().lower()
        if emotion not in EMOTIONS:
            continue
        lex.setdefault(word, set()).add(emotion)
    return lex


TOKEN_RE = re.compile(r"[a-z]+")


def tokenize(text: str) -> list[str]:
    """Lowercase and split on non-alphabetic characters."""
    return TOKEN_RE.findall((text or "").lower())


def score_review(title: str, body: str, lex: dict[str, set[str]]) -> dict:
    tokens = tokenize(title + " " + (body or ""))
    scores = Counter()
    matched_words: dict[str, list[str]] = {e: [] for e in EMOTIONS}
    for tok in tokens:
        emos = lex.get(tok)
        if not emos:
            continue
        for e in emos:
            scores[e] += 1
            if tok not in matched_words[e]:
                matched_words[e].append(tok)

    total = sum(scores.values())
    zero_match = total == 0
    primary = None
    tie_resolved = False
    fallback_used = False
    if zero_match:
        primary = FALLBACK_EMOTION
        fallback_used = True
    else:
        max_score = max(scores.values())
        winners = [e for e in EMOTIONS if scores[e] == max_score]
        tie_resolved = len(winners) > 1
        primary = winners[0]  # canonical-order tie-break (first among maxima)
    return {
        "scores": {e: scores[e] for e in EMOTIONS},
        "matched_words": matched_words,
        "n_tokens": len(tokens),
        "primary": primary,
        "tie_resolved": tie_resolved,
        "zero_match": zero_match,
        "fallback_used": fallback_used,
    }


def main() -> int:
    lex = load_lexicon(LEXICON_PATH)
    records = first_n_records(NUM_REVIEWS)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    # wipe the output file so a fresh run is clean (NRC is deterministic, no resume needed)
    OUT_JSONL.write_text("", encoding="utf-8")

    results = []
    for i, rec in enumerate(records, start=1):
        title = (rec.get("title") or "").strip()
        text = (rec.get("text") or "").strip()
        sc = score_review(title, text, lex)
        row = {
            "row": i,
            "title": title,
            "text": text,
            "n_tokens": sc["n_tokens"],
            "scores": sc["scores"],
            "matched_words": sc["matched_words"],
            "primary": sc["primary"],
            "tie_resolved": sc["tie_resolved"],
            "zero_match": sc["zero_match"],
            "fallback_used": sc["fallback_used"],
        }
        results.append(row)
        with open(OUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    metadata = {
        "experiment": "Step 5B NRC word-list primary emotion (first 100 records)",
        "lexicon": {
            "name": "NRC Emotion Lexicon (EmoLex) v0.92, word-level",
            "source": "https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm",
            "file": "lexicon/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt",
            "citation": "Mohammad & Turney (2013), Computational Intelligence 29(3), 524-545",
            "license": "non-commercial research / educational use (see lexicon/LICENSE-NOTICE.md)",
        },
        "emotions": list(EMOTIONS),
        "tokenization": "lowercase; split on runs of non-alphabetic characters",
        "scoring": "+1 per emotion per matched lexicon word (association flag==1)",
        "primary_rule": "highest total count",
        "tie_rule": "ties -> first in canonical order "
                    "(anger, anticipation, disgust, fear, joy, sadness, surprise, trust) "
                    "among tied maxima",
        "zero_match_rule": f"fallback primary = '{FALLBACK_EMOTION}', fallback_used=True (reported)",
        "independent_of": ["rating", "LLM prediction", "LLM emotion", "expected sentiment"],
        "num_reviews": NUM_REVIEWS,
    }
    META_JSON.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # Console summary
    from collections import Counter
    prim = Counter(r["primary"] for r in results)
    ties = sum(1 for r in results if r["tie_resolved"])
    zm = sum(1 for r in results if r["zero_match"])
    print("=== STEP 5B NRC WORD-LIST EMOTION ===")
    print(f"lexicon entries (8-emotion): {len(lex)}")
    print("NRC primary emotion distribution:")
    for e in EMOTIONS:
        print(f"  {e:<13} {prim.get(e,0)}")
    print(f"tie_resolved         : {ties}")
    print(f"zero_match           : {zm} (fallback_used={sum(1 for r in results if r['fallback_used'])})")
    if zm:
        zr = [r["row"] for r in results if r["zero_match"]]
        print(f"zero-match rows      : {zr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
