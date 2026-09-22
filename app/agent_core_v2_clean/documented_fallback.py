from __future__ import annotations

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
    title=str(evidence[0].get("title") or evidence[0].get("source") or "Documento")
    pages=_pages(evidence)
    reference=title+(f", páginas {pages}" if pages else "")
    text="Encontré documentación directamente relacionada, pero no pude completar una síntesis segura en este turno. Para no publicar fragmentos crudos ni convertir páginas aisladas en pasos, conserva esta referencia y vuelve a intentar la consulta."
    text += "\n\n**Fuente documental**\n- " + reference
    return {"text":text,"mode":"documented_safe_defer","knowledge_used":False,"finish_reason":"safe_defer","documented_evidence_used":True,"internal_knowledge_used":False,"knowledge_mode":"documented_only","degraded":True,"degraded_reason":str(reason or "provider_degraded")}
