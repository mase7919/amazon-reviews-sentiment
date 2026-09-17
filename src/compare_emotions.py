#!/usr/bin/env python3
"""Step 5: compare the two independent primary-emotion methods (LLM vs NRC word list).

Neither method is treated as ground truth -- this is an AGREEMENT/comparison
between two different approaches. Reads the saved outputs from Step 5A (LLM) and
5B (NRC) and produces results/step5_comparison.json plus a console report.

Totals are validated: the agreement matrix must sum to 100 and each method's
distribution to 100.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from classify import EMOTIONS

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
LLM_JSONL = RESULTS / "step5_llm.jsonl"
NRC_JSONL = RESULTS / "step5_nrc.jsonl"
OUT_JSON = RESULTS / "step5_comparison.json"


def load_rows(path: Path) -> dict[int, dict]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["row"]] = r
    return out


def main() -> int:
    llm = load_rows(LLM_JSONL)
    nrc = load_rows(NRC_JSONL)
    rows = sorted(set(llm) & set(nrc))
    total = len(rows)

    # per-emotion agreement (by emotion value)
    agree_by_emotion = Counter()
    diffs = []
    llm_dist = Counter()
    nrc_dist = Counter()
    llm_failed = 0

    for i in rows:
        le = llm[i].get("emotion")
        ne = nrc[i].get("primary")
        if llm[i].get("error"):
            llm_failed += 1
        if le is not None:
            llm_dist[le] += 1
        nrc_dist[ne] += 1
        if le == ne:
            agree_by_emotion[le if le is not None else "(none)"] += 1
        else:
            diffs.append({
                "row": i,
                "title": llm[i].get("title"),
                "text": llm[i].get("text"),
                "llm_emotion": le,
                "nrc_emotion": ne,
                "nrc_scores": nrc[i].get("scores"),
                "nrc_primary_note": ("zero_match" if nrc[i].get("zero_match")
                                     else ("tie" if nrc[i].get("tie_resolved") else "clear")),
            })

    agree = total - len(diffs)
    # 8x8 matrix: rows = LLM emotion, columns = NRC emotion
    matrix = {le: {ne: 0 for ne in EMOTIONS} for le in EMOTIONS}
    for i in rows:
        le = llm[i].get("emotion")
        ne = nrc[i].get("primary")
        if le in matrix and ne in EMOTIONS:
            matrix[le][ne] += 1

    nrc_ties = sum(1 for i in rows if nrc[i].get("tie_resolved"))
    nrc_zero = sum(1 for i in rows if nrc[i].get("zero_match"))
    nrc_fallback = sum(1 for i in rows if nrc[i].get("fallback_used"))

    # validate sums
    matrix_total = sum(sum(row.values()) for row in matrix.values())
    llm_dist_total = sum(llm_dist.values())
    nrc_dist_total = sum(nrc_dist.values())

    result = {
        "total_reviews": total,
        "llm_emotion_equals_nrc": agree,
        "llm_emotion_equals_nrc_pct": round(100.0 * agree / total, 2) if total else 0.0,
        "differ": len(diffs),
        "differ_pct": round(100.0 * len(diffs) / total, 2) if total else 0.0,
        "agreement_counts_by_emotion": {e: agree_by_emotion.get(e, 0) for e in EMOTIONS},
        "llm_emotion_distribution": {e: llm_dist.get(e, 0) for e in EMOTIONS},
        "nrc_emotion_distribution": {e: nrc_dist.get(e, 0) for e in EMOTIONS},
        "matrix": {"rows_are_LLM": True, "cols_are_NRC": True,
                   "cells_llm_by_nrc": matrix},
        "nrc_zero_match_reviews": nrc_zero,
        "nrc_tie_cases": nrc_ties,
        "nrc_fallback_used": nrc_fallback,
        "llm_failed": llm_failed,
        "validation": {
            "matrix_total": matrix_total,
            "llm_distribution_total": llm_dist_total,
            "nrc_distribution_total": nrc_dist_total,
            "all_totals_equal_100": (matrix_total == total
                                     and llm_dist_total == total
                                     and nrc_dist_total == total),
        },
        "disagreements": diffs,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== STEP 5 COMPARISON: LLM emotion vs NRC emotion ===")
    print(f"total reviews            : {total}")
    print(f"agree                    : {agree}  ({result['llm_emotion_equals_nrc_pct']}%)")
    print(f"differ                   : {len(diffs)}  ({result['differ_pct']}%)")
    print(f"nrc zero-match           : {nrc_zero}   nrc ties: {nrc_ties}   llm failed: {llm_failed}")
    print("\n8x8 matrix (rows=LLM, cols=NRC):")
    hdr = "        " + "".join(f"{e[:4]:>6}" for e in EMOTIONS)
    print(hdr)
    for le in EMOTIONS:
        row = "".join(f"{matrix[le][ne]:>6}" for ne in EMOTIONS)
        print(f"{le[:8]:<8}{row}")
    print(f"\nmatrix total: {matrix_total} | llm total: {llm_dist_total} | nrc total: {nrc_dist_total}")
    print("all totals equal 100:", result["validation"]["all_totals_equal_100"])
    print(f"\nLLM distribution: {result['llm_emotion_distribution']}")
    print(f"NRC distribution:  {result['nrc_emotion_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
