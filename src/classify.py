#!/usr/bin/env python3
"""Reusable single-label sentiment classifier backed by an OpenAI-compatible endpoint.

Reads the model endpoint/credentials ONLY from environment variables and never
prints or stores them:
    OPENAI_API_BASE   e.g. http://host:port/v1
    OPENAI_API_KEY    the API key
    SENTIMENT_MODEL   the model identifier (falls back to OPENAI_MODEL)

The star rating is never part of the input: classify_sentiment() accepts only a
title and a body and sends exactly those two fields to the model.

Response contract: the model must return exactly one of POSITIVE / NEGATIVE.
Any deviation (empty, malformed, or an unknown label) raises a clear error.
"""

from __future__ import annotations

import os
from pathlib import Path

VALID_LABELS = ("POSITIVE", "NEGATIVE")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from a local `.env` file into os.environ.

    Real environment variables already set take precedence. Never returns or
    prints any value -- it only populates os.environ so the rest of the code can
    read them. The `.env` file is git-ignored (see project .gitignore).
    """
    if path is None:
        path = PROJECT_ROOT / ".env"
    if not path.exists():
        return
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_dotenv()

# The Open API-compatible course endpoint for the MBAX 6418 assignment.
# The classifier reads OPENAI_API_BASE from the environment when set, otherwise it
# uses this course endpoint. It deliberately does NOT fall back to any local /
# Hermes provider configuration (which may point at a different port).
COURSE_ENDPOINT = "http://dobolyi.com:9001/v1"

# Path to the reusable prompt artifact (kept in the repo for the GitHub submission).
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "sentiment_prompt.txt"

# Name of the subprocess env vars the runtime session must set for the harness.
ENV_BASE = "OPENAI_API_BASE"
ENV_KEY = "OPENAI_API_KEY"
ENV_MODEL = "SENTIMENT_MODEL"


class MissingEnvError(EnvironmentError):
    """Raised when a required environment variable is absent."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(
            "Required environment variable(s) not set: " + ", ".join(missing)
            + " (set OPENAI_API_BASE, OPENAI_API_KEY, and SENTIMENT_MODEL)."
        )


class InvalidModelLabelError(ValueError):
    """Raised when the model returns anything other than a valid label."""


def read_api_env() -> dict[str, str]:
    """Return {base_url, api_key, model}; raise if key/model are missing.

    base_url: OPENAI_API_BASE if set, else the course endpoint (port 9001).
    It never inherits Hermes's own provider endpoint (port 9000).
    """
    base = (os.environ.get(ENV_BASE) or COURSE_ENDPOINT).strip().rstrip("/")
    key = os.environ.get(ENV_KEY, "").strip()
    model = os.environ.get(ENV_MODEL, "").strip() or os.environ.get("OPENAI_MODEL", "").strip()

    missing = []
    if not key:
        missing.append(ENV_KEY)
    if not model:
        missing.append(ENV_MODEL)
    if missing:
        raise MissingEnvError(["OPENAI_API_BASE(auto: course endpoint)"] + missing)
    return {"base": base, "key": key, "model": model}


def load_prompt(path: Path | None = None) -> str:
    """Read a prompt artifact file (defaults to the Step 1/2 binary prompt)."""
    return (path or PROMPT_PATH).read_text(encoding="utf-8").strip()


def build_messages(prompt: str, title: str, body: str):
    """Build the exact OpenAI message list sent to the model.

    Only the title and body are passed (plus the fixed system prompt). The star
    rating and any rating-derived field are deliberately absent.
    """
    title = (title or "").strip()
    body = (body or "").strip()
    user_content = f"Title: {title}\nText: {body}"
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content},
    ]


def parse_label(raw: str, review_id: str = "?") -> str:
    """Normalize and validate the raw model response into a label token.

    Accepts the exact token, with surrounding whitespace and case variants.
    Raises InvalidModelLabelError on any unexpected content.
    """
    token = (raw or "").strip().upper()
    if token in VALID_LABELS:
        return token
    raise InvalidModelLabelError(
        f"review {review_id}: model returned an invalid label {raw!r} "
        f"(expected exactly one of {VALID_LABELS})"
    )


def make_client(api_cfg: dict[str, str]):
    """Create an OpenAI client for a custom base URL without logging the key."""
    from openai import OpenAI

    return OpenAI(base_url=api_cfg["base"], api_key=api_cfg["key"])


def classify_sentiment(title: str, body: str, *, client=None, model: str | None = None,
                       review_id: str = "?"):
    """Return ("POSITIVE" | "NEGATIVE", raw_text, messages).

    Sends only title + body. The returned `messages` mirror exactly what was sent
    (useful for auditing that no rating leaked into the model input).
    """
    api_cfg = read_api_env()
    model = model or api_cfg["model"]
    prompt = load_prompt()
    messages = build_messages(prompt, title, body)

    if client is None:
        client = make_client(api_cfg)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,
    )
    raw = (response.choices[0].message.content or "").strip()
    label = parse_label(raw, review_id)
    # Return the label, the raw token, and the exact messages for auditing.
    return label, raw, messages


# --- Step 5: combined binary sentiment + primary emotion (strict JSON). ---

EMOTIONS = ("anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust")
EMOTION_PROMPT_PATH = PROJECT_ROOT / "prompts" / "sentiment_emotion_prompt.txt"
THREE_LABELS = ("POSITIVE", "NEUTRAL", "NEGATIVE")
THREE_CLASS_PROMPT_PATH = PROJECT_ROOT / "prompts" / "sentiment_emotion_3class.txt"


def _parse_sentiment_emotion(raw: str, labels, review_id: str = "?") -> dict:
    """Shared strict-JSON parser: validates {sentiment, emotion} against `labels`
    and the eight emotion labels. Extracts the first {...} block from the response.
    """
    import json
    import re

    text = (raw or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise InvalidModelLabelError(
            f"review {review_id}: no JSON object found in response {raw!r}")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise InvalidModelLabelError(f"review {review_id}: malformed JSON {raw!r} ({exc})")
    if not isinstance(obj, dict):
        raise InvalidModelLabelError(f"review {review_id}: response not an object {raw!r}")
    sent = str(obj.get("sentiment", "")).strip().upper()
    emo = str(obj.get("emotion", "")).strip().lower()
    if sent not in labels:
        raise InvalidModelLabelError(
            f"review {review_id}: invalid sentiment {obj.get('sentiment')!r} "
            f"(expected one of {labels})")
    if emo not in EMOTIONS:
        raise InvalidModelLabelError(
            f"review {review_id}: invalid emotion {obj.get('emotion')!r} "
            f"(expected one of {EMOTIONS})")
    return {"sentiment": sent, "emotion": emo}


def parse_sentiment_emotion(raw: str, review_id: str = "?") -> dict:
    """Validate a binary (POSITIVE/NEGATIVE) sentiment + emotion JSON response."""
    return _parse_sentiment_emotion(raw, VALID_LABELS, review_id)


def parse_sentiment_emotion3(raw: str, review_id: str = "?") -> dict:
    """Validate a three-class (POSITIVE/NEUTRAL/NEGATIVE) sentiment + emotion response."""
    return _parse_sentiment_emotion(raw, THREE_LABELS, review_id)


def classify_sentiment_emotion(title: str, body: str, *, client=None,
                               model: str | None = None, review_id: str = "?"):
    """Return ({"sentiment":..., "emotion":...}, raw_text, messages).

    Uses the Step 5 combined prompt (sentiment_emotion_prompt.txt) and sends only
    title + body to the model. Independent of the Step 2 binary classifier.
    """
    api_cfg = read_api_env()
    model = model or api_cfg["model"]
    prompt = load_prompt(EMOTION_PROMPT_PATH)
    messages = build_messages(prompt, title, body)

    if client is None:
        client = make_client(api_cfg)

    response = client.chat.completions.create(
        model=model, messages=messages, temperature=0.0,
    )
    raw = (response.choices[0].message.content or "").strip()
    parsed = parse_sentiment_emotion(raw, review_id)
    return parsed, raw, messages


def classify_sentiment_emotion3(title: str, body: str, *, client=None,
                                model: str | None = None, review_id: str = "?"):
    """Return ({"sentiment": POSITIVE|NEUTRAL|NEGATIVE, "emotion": ...}, raw, messages).

    Uses the Step 6 three-class prompt (sentiment_emotion_3class.txt) and sends
    only title + body to the model. Independent of the binary/Step-5 classifiers.
    """
    api_cfg = read_api_env()
    model = model or api_cfg["model"]
    prompt = load_prompt(THREE_CLASS_PROMPT_PATH)
    messages = build_messages(prompt, title, body)

    if client is None:
        client = make_client(api_cfg)

    response = client.chat.completions.create(
        model=model, messages=messages, temperature=0.0,
    )
    raw = (response.choices[0].message.content or "").strip()
    parsed = parse_sentiment_emotion3(raw, review_id)
    return parsed, raw, messages


if __name__ == "__main__":
    # Lightweight self-test: show the env config status without revealing secrets.
    try:
        cfg = read_api_env()
        print("API env configured: base present=", cfg["base"] != "",
              "| key present=", bool(os.environ.get(ENV_KEY)),
              "| model=", cfg["model"])
    except MissingEnvError as exc:
        print("MISSING ENV:", ", ".join(exc.missing))
