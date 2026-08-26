from __future__ import annotations
import re, unicodedata
URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)

def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9:/._?=&%+\-\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def extract_urls(value: str) -> list[str]:
    result=[]
    for match in URL_RE.findall(str(value or "")):
        clean=match.rstrip(".,;:!?)]}")
        if clean not in result: result.append(clean)
    return result
