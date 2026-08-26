from __future__ import annotations
import re
import unicodedata
from urllib.parse import urldefrag

from app.domain_registry_v1 import PRODUCT_ENTITY_REGISTRY, PROCESS_ENTITY_REGISTRY

URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text)).strip()


def contains_alias(text: str, alias: str) -> bool:
    candidate = normalize(alias)
    return bool(candidate and re.search(rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])", text))


def detect_registry_entities(query: str) -> dict:
    normalized = normalize(query)
    result = {"products": [], "processes": []}
    for key, registry in (("products", PRODUCT_ENTITY_REGISTRY), ("processes", PROCESS_ENTITY_REGISTRY)):
        for entity_id, item in registry.items():
            aliases = [item.get("canonical_name", "")] + list(item.get("aliases") or [])
            if any(contains_alias(normalized, alias) for alias in aliases):
                result[key].append({
                    "entity_id": entity_id,
                    "canonical_name": item.get("canonical_name", entity_id),
                    "retrieval_hints": dict(item.get("retrieval_hints") or {}),
                })
    return result


def extract_exact_url(query: str) -> str | None:
    match = URL_RE.search(str(query or ""))
    if not match: return None
    clean, _ = urldefrag(match.group(0).rstrip(".,;:!?)]}"))
    return clean.rstrip("/")


def build_candidate_queries(query: str) -> dict:
    entities = detect_registry_entities(query)
    exact_url = extract_exact_url(query)
    if exact_url:
        return {"mode": "exact_source", "queries": [query], "exact_url": exact_url, **entities}
    if entities["products"]:
        planned = [f"{query} Producto o herramienta evaluada: {item['canonical_name']}" for item in entities["products"]]
        return {"mode": "split_by_product" if len(planned) > 1 else "entity_enriched", "queries": planned, "exact_url": None, **entities}
    if entities["processes"]:
        planned = [f"{query} Proceso evaluado: {item['canonical_name']}" for item in entities["processes"]]
        return {"mode": "split_by_process" if len(planned) > 1 else "entity_enriched", "queries": planned, "exact_url": None, **entities}
    return {"mode": "unmodified", "queries": [query], "exact_url": None, **entities}
