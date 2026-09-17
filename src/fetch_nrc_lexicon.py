#!/usr/bin/env python3
"""Download the NRC Emotion Lexicon (EmoLex) v0.92 from Saif Mohammad's official
page into lexicon/ so the project is reproducible WITHOUT committing NRC material
(see lexicon/LICENSE-NOTICE.md — the NRC EULA §3.1 prohibits redistributing the
lexicon file itself; it is downloaded on demand, not stored in Git).

Run once before running the NRC scoring scripts:
    python src/fetch_nrc_lexicon.py

Downloads: https://saifmohammad.com/WebDocs/NRC-Emotion-Lexicon.zip
Extracts (into lexicon/):
    NRC-Emotion-Lexicon-Wordlevel-v0.92.txt   (the word-level lexicon we score with)
    README.txt / readme.txt / EULA PDF        (license/reference material)
"""

from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEX = ROOT / "lexicon"
SRC = "https://saifmohammad.com/WebDocs/NRC-Emotion-Lexicon.zip"

FILE_TARGETS = {
    "NRC-Emotion-Lexicon/NRC-Emotion-Lexicon-v0.92/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt":
        "NRC-Emotion-Lexicon-Wordlevel-v0.92.txt",
    "NRC-Emotion-Lexicon/README.txt": "README.txt",
    "NRC-Emotion-Lexicon/NRC-Emotion-Lexicon-v0.92/readme.txt": "readme.txt",
    "NRC-Emotion-Lexicon/NRC - Sentiment Lexicon - Research EULA Sept 2017 .pdf":
        "NRC - Sentiment Lexicon - Research EULA Sept 2017 .pdf",
}


def main() -> int:
    LEX.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {SRC}")
    req = urllib.request.Request(SRC, headers={"User-Agent": "amazon-review-sentiment/0.1"})
    data = urllib.request.urlopen(req, timeout=120).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    for member, out_name in FILE_TARGETS.items():
        if member not in z.namelist():
            print(f"  !! missing in archive: {member}")
            continue
        (LEX / out_name).write_bytes(z.read(member))
        print(f"  extracted {out_name}")
    print("Done. The lexicon data files are git-ignored (reproducible via this script).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
