from __future__ import annotations
from .source_footer import compact_sources

def _pages(items):
    values=[]
    for item in items:
        page=str(item.get("page") or "").strip()
        if page and page not in values:
            values.append(page)
    return ", ".join(values)

def build_documented_fallback(retrieval,reason="provider_degraded"):
    evidence=list((retrieval or {}).get("generation_evidence") or (retrieval or {}).get("evidence") or [])
    if not evidence:
        return None
    text="Encontré documentación directamente relacionada, pero no pude completar una síntesis segura en este turno. Para no publicar fragmentos crudos ni convertir páginas aisladas en pasos, conserva esta referencia y vuelve a intentar la consulta."
    cited=[str(x.get("id")) for x in evidence if x.get("id")]
    footer=compact_sources(evidence,cited)
    if footer:text += "\n\n" + footer
    return {"text":text,"mode":"documented_safe_defer","knowledge_used":False,"finish_reason":"safe_defer","documented_evidence_used":True,"internal_knowledge_used":False,"knowledge_mode":"documented_only","degraded":True,"degraded_reason":str(reason or "provider_degraded")}
