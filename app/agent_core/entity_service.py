from __future__ import annotations
import re
from app.agent_core.router_normalizer import normalize_text
from app.domain_registry_v1 import PRODUCT_ENTITY_REGISTRY, PROCESS_ENTITY_REGISTRY

def contains_alias(text: str, alias: str) -> bool:
    candidate=normalize_text(alias)
    return bool(candidate and re.search(rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])", text))

def detect_from_registry(message: str, registry: dict) -> list[dict]:
    text=normalize_text(message); result=[]
    for entity_id,item in registry.items():
        aliases=[item.get("canonical_name","")]+list(item.get("aliases") or [])
        if any(contains_alias(text,alias) for alias in aliases):
            result.append({"entity_id":entity_id,"canonical_name":str(item.get("canonical_name") or entity_id),"retrieval_hints":dict(item.get("retrieval_hints") or {})})
    return result

def detect_entities(message: str) -> dict:
    return {"products":detect_from_registry(message,PRODUCT_ENTITY_REGISTRY),"processes":detect_from_registry(message,PROCESS_ENTITY_REGISTRY)}
