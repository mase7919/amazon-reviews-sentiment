# NRC Emotion Lexicon — source, license & redistribution notice

This project uses the **NRC Emotion Lexicon (EmoLex), version 0.92** (word-level)
for word-list emotion scoring (Step 5B / Step 6), originally published at
https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm.

## Source
- Resource: NRC Emotion Lexicon (word-level), v0.92
- Publisher: National Research Council Canada (NRC) — Saif M. Mohammad & Peter D. Turney
- Original page: https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm
- Download: `NRC-Emotion-Lexicon.zip` from
  https://saifmohammad.com/WebDocs/NRC-Emotion-Lexicon.zip

## Term "Lexicon" / "Licensed Product"
Per the NRC licence ("NRC Sentiment Lexicons Single Product End-User Licence
Agreement", September 2017, §3.1):

> "Use of the Licensed Product is personal to You and **You will not give access to
> or disclose, either in whole or in part, the Licensed Product to any other party
> without the prior written consent of NRC.**"

Because a public GitHub repository counts as disclosing the licensed material to a
third party, **the lexicon data file is NOT included in this repository.**

## How this repository stays reproducible without redistributing the file
- `src/fetch_nrc_lexicon.py` downloads and extracts the lexicon (and the NRC
  README / EULA) into `lexicon/`. The score/compare scripts read it from there.
- The downloaded files are **git-ignored** (`lexicon/*.txt`, `lexicon/*.pdf`).
- Run `python src/fetch_nrc_lexicon.py` once before running the NRC scoring steps,
  or download the file directly from the source above.

## Citation
> Saif M. Mohammad and Peter D. Turney. (2013). *Crowdsourcing a Word-Emotion
> Association Lexicon.* Computational Intelligence, 29(3), 524–545.
> https://doi.org/10.1111/j.1467-8640.2012.00460.x

Use of the lexicon in this project is for non-commercial, educational research
(the assignment for which it was obtained). This notice documents attribution and
the redistribution restriction; it is not a re-licensing of NRC material.
