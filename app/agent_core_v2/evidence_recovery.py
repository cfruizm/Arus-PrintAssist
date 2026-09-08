from __future__ import annotations
from typing import Any

FAILURE_REASONS={
 "provider_unavailable","provider_rate_limited","session_token_budget_exhausted",
 "answer_truncated","answer_invalid","answer_empty","answer_schema_error","unknown_generation_failure"
}

def classify_generation_failure(*, error: Exception | None=None, finish_reason: str | None=None, answer_text: str | None=None) -> str | None:
    text=str(error or "").lower(); answer=str(answer_text or "").strip()
    if any(x in text for x in ("session token", "límite de tokens de la sesión", "token budget")): return "session_token_budget_exhausted"
    if any(x in text for x in ("rate limit", "429", "too many requests")): return "provider_rate_limited"
    if any(x in text for x in ("connection", "unavailable", "timeout", "503", "504")): return "provider_unavailable"
    if finish_reason == "length": return "answer_truncated"
    if not answer and error is None: return "answer_empty"
    return "unknown_generation_failure" if error else None

def _source_label(item: dict[str, Any]) -> str:
    md=item.get("metadata") or {}; title=str(item.get("title") or md.get("title") or "Fuente documental")
    url=str(item.get("url") or md.get("canonical_url") or md.get("source_url") or md.get("source") or "")
    return f"{title} | {url}" if url else title

def build_evidence_backed_recovery(selection: dict[str, Any], *, failure_reason: str) -> dict[str, Any]:
    selected=selection.get("selected") or []
    claims=[]; conditions=[]; sources=[]
    for item in selected:
        assessment=item.get("semantic_assessment") or {}
        for claim in assessment.get("supported_claims") or []:
            claim=" ".join(str(claim).split())
            if claim and claim not in claims: claims.append(claim)
        for condition in assessment.get("conditions") or []:
            condition=" ".join(str(condition).split())
            if condition and condition not in conditions: conditions.append(condition)
        label=_source_label(item)
        if label not in sources: sources.append(label)
    if not claims:
        for item in selected:
            text=" ".join(str(item.get("text") or "").split())
            if text: claims.append(text[:700])
    if not claims:
        return {"mode":"generation_failure_without_evidence","text":"No fue posible generar la respuesta y no hay evidencia aprobada suficiente para una recuperación segura.","citations":[],"fallback_reason":failure_reason,"knowledge_used":False}
    body="### Información documentada\n\n" + "\n\n".join(f"- {c}" for c in claims[:6])
    if conditions: body += "\n\n### Alcance y condiciones\n\n" + "\n".join(f"- {c}" for c in conditions[:4])
    body += "\n\n### Fuentes\n\n" + "\n".join(f"- {s}" for s in sources[:4])
    return {"mode":"evidence_backed_recovery","text":body,"citations":selection.get("selected_ids") or [],"fallback_reason":failure_reason,"knowledge_used":False}
