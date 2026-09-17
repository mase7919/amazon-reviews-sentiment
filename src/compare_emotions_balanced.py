#!/usr/bin/env python3
"""Step 6: compare LLM vs NRC primary emotion on the balanced 150-review sample.

Also reports a DIAGNOSTIC agreement rate computed only over reviews where NRC has
a UNIQUE, NONZERO maximum emotion score (i.e. no tie and at least one matched word).
This is supplementary and does not replace the overall agreement rate.

Outputs: results/step6_emotion_comparison.json (+ console report).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from classify import EMOTIONS

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
LLM_JSONL = RESULTS / "step6_llm.jsonl"
NRC_JSONL = RESULTS / "step6_nrc.jsonl"
OUT = RESULTS / "step6_emotion_comparison.json"


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

    agree_by = Counter(); diffs = []; llm_dist = Counter(); nrc_dist = Counter()
    llm_failed = 0; matrix = {le: {ne: 0 for ne in EMOTIONS} for le in EMOTIONS}

    # diagnostic subset: NRC unique nonzero maximum (no tie, >=1 matched word)
    diag_rows = []
    for i in rows:
        s = nrc[i]["scores"]
        mx = max(s.values())
        if mx > 0 and list(s.values()).count(mx) == 1:
            diag_rows.append(i)

    for i in rows:
        le = llm[i].get("llm_emotion"); ne = nrc[i].get("primary")
        if llm[i].get("error"): llm_failed += 1
        if le is not None: llm_dist[le] += 1
        nrc_dist[ne] += 1
        if le == ne:
            agree_by[le if le is not None else "(none)"] += 1
        if le in matrix and ne in EMOTIONS:
            matrix[le][ne] += 1
        if le != ne:
            diffs.append({"row": i, "title": llm[i].get("title"), "text": llm[i].get("text"),
                          "llm_emotion": le, "nrc_emotion": ne,
                          "nrc_primary_note": ("zero_match" if nrc[i].get("zero_match")
                                               else ("tie" if nrc[i].get("tie_resolved") else "unique"))})

    agree = total - len(diffs)
    # diagnostic agreement on unique-nonzero-NRC subset
    diag_agree = sum(1 for i in diag_rows if llm[i].get("llm_emotion") == nrc[i].get("primary"))

    nrc_ties = sum(1 for i in rows if nrc[i].get("tie_resolved"))
    nrc_zero = sum(1 for i in rows if nrc[i].get("zero_match"))
    matrix_total = sum(sum(x.values()) for x in matrix.values())

    result = {
        "experiment": "Step 6 LLM vs NRC emotion comparison (balanced 150)",
        "total_reviews": total,
        "llm_emotion_equals_nrc": agree,
        "llm_emotion_equals_nrc_pct": round(100.0 * agree / total, 2),
        "differ": len(diffs),
        "differ_pct": round(100.0 * len(diffs) / total, 2),
        "agreement_counts_by_emotion": {e: agree_by.get(e, 0) for e in EMOTIONS},
        "llm_emotion_distribution": {e: llm_dist.get(e, 0) for e in EMOTIONS},
        "nrc_emotion_distribution": {e: nrc_dist.get(e, 0) for e in EMOTIONS},
        "matrix_llm_by_nrc": matrix,
        "matrix_total": matrix_total,
        "nrc_tie_cases": nrc_ties,
        "nrc_zero_match_reviews": nrc_zero,
        "nrc_fallback_used": sum(1 for i in rows if nrc[i].get("fallback_used")),
        "llm_failed": llm_failed,
        "diagnostic": {
            "note": "subset where NRC has a unique, nonzero maximum emotion score",
            "n": len(diag_rows),
            "agreement_on_subset": diag_agree,
            "agreement_on_subset_pct": round(100.0 * diag_agree / len(diag_rows), 2)
            if diag_rows else 0.0,
        },
        "validation": {
            "matrix_total": matrix_total,
            "llm_distribution_total": sum(llm_dist.values()),
            "nrc_distribution_total": sum(nrc_dist.values()),
            "all_totals_equal_150": (matrix_total == total
                                     and sum(llm_dist.values()) == total
                                     and sum(nrc_dist.values()) == total),
        },
        "disagreements": diffs,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== STEP 6 EMOTION COMPARISON (LLM vs NRC, balanced 150) ===")
    print(f"total            : {total}")
    print(f"agree            : {agree} ({result['llm_emotion_equals_nrc_pct']}%)")
    print(f"differ           : {len(diffs)} ({result['differ_pct']}%)")
    print(f"NRC ties         : {nrc_ties}   zero-match: {nrc_zero}   LLM failed: {llm_failed}")
    d = result["diagnostic"]
    print(f"diagnostic (unique nonzero NRC): n={d['n']}, agree={d['agreement_on_subset']} "
          f"({d['agreement_on_subset_pct']}%)")
    print("\n8x8 matrix (rows=LLM, cols=NRC):")
    print("        " + "".join(f"{e[:4]:>6}" for e in EMOTIONS))
    for le in EMOTIONS:
        print(f"{le[:8]:<8}" + "".join(f"{matrix[le][ne]:>6}" for ne in EMOTIONS))
    print(f"\nmatrix total {matrix_total} | llm {sum(llm_dist.values())} | nrc {sum(nrc_dist.values())}")
    print("totals==150:", result["validation"]["all_totals_equal_150"])
    print("LLM dist:", result["llm_emotion_distribution"])
    print("NRC dist: ", result["nrc_emotion_distribution"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
