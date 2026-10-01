from __future__ import annotations

import re
import unicodedata
from collections import Counter

_COMMON = {
    "cual", "cuales", "esos", "esas", "este", "esta", "estos", "estas",
    "utiliza", "utilizan", "usar", "usan", "tiene", "tienen", "para", "sobre",
    "which", "what", "those", "these", "uses", "using", "with", "that",
}


def _norm(value):
    return " ".join(
        "".join(
            char
            for char in unicodedata.normalize("NFKD", str(value or "").casefold())
            if not unicodedata.combining(char)
        ).split()
    )


def _query_terms(message, understanding):
    subject = _norm((understanding or {}).get("canonical_subject") or "")
    subject_terms = set(re.findall(r"[a-z0-9]+", subject))
    raw = re.findall(r"[A-Za-z0-9]+", str(message or ""))
    out = []
    for original in raw:
        term = _norm(original)
        if len(term) < 2 or term in _COMMON or term in subject_terms:
            continue
        out.append((term, bool(original.isupper() and len(original) <= 8)))
    return out


def _segments(evidence):
    rows = []
    for item in evidence or []:
        text = " ".join(str(item.get("text") or "").split())
        if not text:
            continue
        pieces = re.split(r"(?<=[.!?;:])\s+|(?=\b\d{2,6}\b)", text)
        for piece in pieces:
            piece = " ".join(piece.split()).strip(" -|\t")
            if len(piece) >= 12:
                rows.append({"id": str(item.get("id") or ""), "text": piece})
    return rows


def _best_property_terms(message, understanding, segments):
    query = _query_terms(message, understanding)
    if not query:
        return []
    frequencies = Counter()
    for term, _ in query:
        frequencies[term] = sum(1 for row in segments if term in _norm(row["text"]))
    candidates = [(term, acronym, frequencies[term]) for term, acronym in query if frequencies[term] > 0]
    if not candidates:
        return []
    candidates.sort(key=lambda value: (0 if value[1] else 1, value[2], len(value[0])))
    best = candidates[0]
    return [term for term, acronym, freq in candidates if acronym == best[1] and freq == best[2]][:2]


def _numeric_facts(segments, property_terms):
    facts = {}
    for row in segments:
        normalized = _norm(row["text"])
        if not property_terms or not any(term in normalized for term in property_terms):
            continue
        for value in re.findall(r"(?<![A-Za-z0-9])\d{2,6}(?![A-Za-z0-9])", row["text"]):
            current = facts.get(value)
            if current is None or len(row["text"]) < len(current["text"]):
                facts[value] = row
    return facts


def ensure_enumerated_fact_coverage(text, message, understanding, evidence):
    """Repair a strict subset of explicit numeric facts for a queried property.

    The guard is narrow and product-agnostic. It activates only when authorized
    evidence contains between two and eight distinct numeric facts associated with
    the same high-information query property and the answer contains a strict subset.
    """
    segments = _segments(evidence)
    property_terms = _best_property_terms(message, understanding, segments)
    facts = _numeric_facts(segments, property_terms)
    response_numbers = set(re.findall(r"(?<![A-Za-z0-9])\d{2,6}(?![A-Za-z0-9])", str(text or "")))
    missing = sorted(set(facts) - response_numbers, key=lambda value: int(value))
    diagnostic = {
        "checked": bool(property_terms),
        "property_terms": property_terms,
        "documented_fact_count": len(facts),
        "documented_values": sorted(facts, key=lambda value: int(value)),
        "response_values": sorted(response_numbers, key=lambda value: int(value)),
        "missing_values": missing,
        "repaired": False,
    }
    if len(facts) < 2 or not response_numbers or not missing or len(facts) > 8 or len(missing) > 4:
        return str(text or ""), diagnostic

    additions = []
    for value in missing:
        row = facts[value]
        snippet = " ".join(row["text"].split())
        if len(snippet) > 220:
            snippet = snippet[:217].rsplit(" ", 1)[0] + "..."
        citation = f" [{row['id']}]" if row.get("id") else ""
        additions.append(f"- {snippet}{citation}")
    if additions:
        repaired = str(text or "").rstrip() + "\n\n**Cobertura documental adicional**\n" + "\n".join(additions)
        diagnostic["repaired"] = True
        return repaired, diagnostic
    return str(text or ""), diagnostic
