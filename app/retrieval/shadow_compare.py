from __future__ import annotations
from urllib.parse import urldefrag
from app.agent_core.models import ShadowResult
from app.agent_core.entity_adapter import detect
from app.domain_registry_v1 import PRODUCT_ENTITY_REGISTRY, PROCESS_ENTITY_REGISTRY

def source_key(doc):
    md=getattr(doc,"metadata",{}) or {}; return str(md.get("canonical_url") or md.get("source_url") or md.get("source") or md.get("title") or "")
def exact_url(message):
    import re
    m=re.search(r"https?://[^\s<>()]+",str(message or "")); return urldefrag(m.group(0).rstrip(".,;!?"))[0].rstrip("/") if m else None

def compare_retrieval(query, legacy_callable, candidate_callable):
    result=ShadowResult(query=query)
    result.detected_products=detect(query,PRODUCT_ENTITY_REGISTRY)
    result.detected_processes=detect(query,PROCESS_ENTITY_REGISTRY)
    try: legacy=list(legacy_callable(query) or [])
    except Exception as exc: legacy=[]; result.legacy_error=f"{type(exc).__name__}: {exc}"
    try: candidate=list(candidate_callable(query,result.detected_products,result.detected_processes,exact_url(query)) or [])
    except Exception as exc: candidate=[]; result.candidate_error=f"{type(exc).__name__}: {exc}"
    result.legacy_sources=[source_key(d) for d in legacy if source_key(d)]
    result.candidate_sources=[source_key(d) for d in candidate if source_key(d)]
    result.top1_match=bool(result.legacy_sources and result.candidate_sources and result.legacy_sources[0]==result.candidate_sources[0])
    left=set(result.legacy_sources[:3]); right=set(result.candidate_sources[:3]); result.top3_overlap=len(left & right)/max(1,len(left | right))
    url=exact_url(query)
    if url:
        result.exact_source_respected=all(s.rstrip("/")==url for s in result.candidate_sources) if result.candidate_sources else True
    return result
