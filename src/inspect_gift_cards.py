#!/usr/bin/env python3
"""Setup-milestone script: download (if needed) and inspect the Amazon Reviews '23
Gift Cards review file.

Reads directly from the gzipped JSON Lines file, streaming one pass, so we can
count every review without loading it all into memory. Uses only the standard
library. No model/API calls, no sentiment classification here.

Usage:
    python src/inspect_gift_cards.py [--preview N] [--data-dir data]

Args:
    --preview N   Number of review records to print in human-readable form (default 3).
    --data-dir    Directory in which to store the download (default: ./data).
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import sys
import urllib.request

# Data source specified in MBAX 6418 Assignment 1 (Amazon Reviews '23, McAuley Lab).
SOURCE_URL = (
    "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/"
    "review_categories/Gift_Cards.jsonl.gz"
)
DEFAULT_FILENAME = "Gift_Cards.jsonl.gz"

# Fields documented in the assignment's expected schema.
EXPECTED_FIELDS = {
    "rating",
    "title",
    "text",
    "verified_purchase",
    "helpful_vote",
    "timestamp",
    "images",
    "asin",
    "parent_asin",
    "user_id",
}


def _download(url: str, dest: str) -> None:
    """Download `url` to `dest` in a streaming copy."""
    print(f"[download] source : {url}")
    print(f"[download] writing to {dest}")
    # Default User-Agent can be rejected by some hosts; identify ourselves.
    request = urllib.request.Request(url, headers={"User-Agent": "amazon-reviews-sentiment/0.1"})
    with urllib.request.urlopen(request, timeout=120) as resp, open(dest, "wb") as out:
        import shutil
        shutil.copyfileobj(resp, out, length=1024 * 256)
        sys.stdout.write("\n")
        sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Download + inspect Amazon Gift Cards reviews.")
    parser.add_argument("--preview", type=int, default=3, help="Number of reviews to print (default 3).")
    parser.add_argument("--data-dir", default="data", help="Directory for the raw data file.")
    args = parser.parse_args()

    data_dir = args.data_dir
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, DEFAULT_FILENAME)

    # 1) Download only if not already present.
    if not os.path.exists(path):
        _download(SOURCE_URL, path)
    else:
        print(f"[data] already present: {path}")

    size_bytes = os.path.getsize(path)
    print(f"[data] compressed size on disk   : {size_bytes:,} bytes ({size_bytes/1e6:,.1f} MB)")

    # 2) Stream one pass through the gzipped JSONL: count records, collect fields,
    #    hold onto the first `preview` records for display.
    count = 0
    empty_text = 0
    field_counter: dict[str, int] = {}
    preview: list[dict] = []
    line_errors = 0
    first_error_line = None

    with gzip.open(path, "rt", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                line_errors += 1
                if first_error_line is None:
                    first_error_line = lineno
                continue

            count += 1
            if isinstance(record, dict):
                for key in record.keys():
                    field_counter[key] = field_counter.get(key, 0) + 1
                if not (record.get("text") or "").strip():
                    empty_text += 1
                if len(preview) < args.preview:
                    preview.append(record)
            else:
                line_errors += 1
                if first_error_line is None:
                    first_error_line = lineno

    # 3) Report.
    print("\n=== SUMMARY ===")
    print(f"total review records parsed : {count:,}")
    print(f"records with empty text     : {empty_text:,}")

    if line_errors:
        print(f"!! lines that failed to parse : {line_errors:,} (first at line {first_error_line})")
    else:
        print("JSON parse errors            : 0")

    observed = set(field_counter)
    print("\n=== FIELD NAMES (present in at least one record) ===")
    for name in sorted(observed):
        mark = "" if name in EXPECTED_FIELDS else "   <-- not in assignment schema"
        print(f"  {name:<22} {field_counter[name]:>10,} records{mark}")
    missing = EXPECTED_FIELDS - observed
    if missing:
        print(f"  (assignment fields NOT observed: {sorted(missing)})")

    print("\n=== PREVIEW REVIEWS ===")
    if preview:
        for i, rec in enumerate(preview, start=1):
            text = (rec.get("text") or "").strip()
            print(f"\n--- review #{i} ---")
            print(f"  rating           : {rec.get('rating')}")
            print(f"  title            : {rec.get('title')}")
            print(f"  verified_purchase: {rec.get('verified_purchase')}")
            print(f"  helpful_vote     : {rec.get('helpful_vote')}")
            print(f"  timestamp        : {rec.get('timestamp')}")
            print(f"  asin             : {rec.get('asin')}")
            print(f"  parent_asin      : {rec.get('parent_asin')}")
            print(f"  user_id          : {rec.get('user_id')}")
            print(f"  #images          : {len(rec.get('images') or [])}")
            print(f"  text ({len(text)} chars): {text[:280]}{'…' if len(text) > 280 else ''}")
    else:
        print("  (no records were parsed)")

    print("\n=== DONE ===")
    return 0 if line_errors == 0 and count > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
