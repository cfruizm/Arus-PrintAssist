from __future__ import annotations
import re
import unicodedata

URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
POLITENESS_PREFIXES = (
    "por favor ", "porfa ", "favor ",
)
POLITENESS_SUFFIXES = (
    " por favor", " porfa", " gracias",
)


def normalize_conversation_text(value: str) -> str:
    """Normalize conversational text without damaging URLs.

    URL extraction must always run against the original message. This function
    intentionally removes conversational punctuation, accents and extra spaces.
    """
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_politeness(value: str) -> str:
    text = normalize_conversation_text(value)
    changed = True
    while changed:
        changed = False
        for prefix in POLITENESS_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):].strip(); changed = True
        for suffix in POLITENESS_SUFFIXES:
            if text.endswith(suffix):
                text = text[:-len(suffix)].strip(); changed = True
    return text


def extract_urls(value: str) -> list[str]:
    result = []
    for match in URL_RE.findall(str(value or "")):
        clean = match.rstrip(".,;:!?)]}")
        if clean not in result: result.append(clean)
    return result

# Backward-compatible alias for Stage 5A imports.
normalize_text = normalize_conversation_text
