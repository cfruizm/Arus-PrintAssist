from __future__ import annotations
from copy import deepcopy
import re
import unicodedata

_GENERIC = {
    "como", "para", "una", "uno", "unos", "unas", "que", "cual", "cuales",
    "existen", "documentados", "documentacion", "informacion", "usuario",
    "proceso", "procedimiento", "metodo", "metodos", "detalle", "detallar",
    "realizar", "realiza", "actual", "explicar", "analizar", "saber", "muestra",
    "necesito", "quiero", "puedo", "dime", "hacer", "obtener", "comprender",
    "the", "how", "for", "documented", "information", "process", "method",
}
_SHORT = {"pin", "ews", "usb", "smb", "wja", "ipp", "pcl", "pdf", "mf", "dca", "sds"}
_OPERATION = {
    "asignar", "consultar", "actualizar", "instalar", "configurar", "analizar",
    "mostrar", "generar", "exportar", "comparar", "validar", "recuperar",
    "descargar", "importar", "crear", "visualizar", "listar", "resumir",
    "distribuir", "distribucion", "procesar", "ejecutar", "escanear",
}

def _norm(value):
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()

def _tokens(value):
    out = set()
    for token in re.findall(r"[a-z0-9]+", _norm(value)):
        if token in _GENERIC:
            continue
        if len(token) >= 4 or token in _SHORT:
            out.add(token)
    return out

def _identity(item):
    return str(item.get("url") or item.get("source") or (item.get("metadata") or {}).get("canonical_url") or item.get("title") or "")

def _dedup(items):
    out, seen = [], set()
    for item in items:
        key = (_identity(item), str(item.get("page") or ""), _norm(item.get("text"))[:320])
        if key in seen:
            continue
        seen.add(key)
        out.append(deepcopy(item))
    return out

def _request_text(message, understanding, retrieval):
    understanding = understanding or {}
    # A degraded provider contract cannot safely contribute memory-derived goals.
    if understanding.get("degraded"):
        return str(message or "")
    fields = ((retrieval.get("query") or {}).get("fields") or {})
    relation = str(fields.get("topic_relation") or understanding.get("topic_relation") or "")
    if relation == "new_topic":
        return " ".join((str(message or ""), str(understanding.get("current_goal") or "")))
    updates = understanding.get("goal_updates") or {}
    return " ".join(str(x or "") for x in (
        message, understanding.get("current_goal"), updates.get("operation"),
        updates.get("subject"), updates.get("product"), fields.get("contextual_operation"),
    ))

def _fit(item, wanted):
    title = _tokens(item.get("title"))
    content = title | _tokens(item.get("text"))
    covered = wanted & content
    title_hits = wanted & title
    semantic = float((item.get("semantic_fit") or {}).get("score", 0) or 0)
    return {
        "coverage": len(covered) / max(1, len(wanted)),
        "title_coverage": len(title_hits) / max(1, len(wanted)),
        "covered_count": len(covered),
        "title_hit_count": len(title_hits),
        "semantic_score": semantic,
        "carried": bool(item.get("carried_from_previous_answer")),
        "covered": sorted(covered),
        "title_hits": sorted(title_hits),
    }

def apply_unified_evidence_verdict(retrieval, message, understanding):
    out = deepcopy(retrieval or {})
    candidates = _dedup(out.get("diagnostic_evidence") or out.get("generation_evidence") or out.get("evidence") or [])
    wanted = _tokens(_request_text(message, understanding, out))
    scored = []
    for item in candidates:
        fit = _fit(item, wanted)
        item["unified_evidence_fit"] = {k: round(v, 4) if isinstance(v, float) else v for k, v in fit.items()}
        scored.append((fit, item))
    scored.sort(key=lambda pair: (
        pair[0]["title_hit_count"], pair[0]["covered_count"], pair[0]["title_coverage"],
        pair[0]["coverage"], pair[0]["semantic_score"], not pair[0]["carried"],
    ), reverse=True)

    selected = []
    accepted = False
    status, mode, reason = "insufficient", "internal_only", "no_operationally_aligned_evidence"
    best_fit, best = scored[0] if scored else ({}, None)
    if best and wanted:
        target_terms = wanted - _OPERATION
        available = _tokens(best.get("title")) | _tokens(best.get("text"))
        requested_short={x for x in wanted if x in _SHORT}
        mandatory_short_ok=not requested_short or requested_short.issubset(available)
        target_ok = (not target_terms or len(target_terms & available)/max(1,len(target_terms)) >= 0.5) and mandatory_short_ok
        request_norm=_norm(message)
        conceptual_definition=bool(re.search(r"\b(que es|what is|define|definir)\b",request_norm))
        body_norm=_norm(" ".join((str(best.get("title") or ""),str(best.get("text") or ""))))
        definition_supported=not conceptual_definition or bool(re.search(r"\b(es un|es una|is a|is an|aplicacion|application|solucion|solution|herramienta|tool)\b",body_norm))
        unrequested_subservice=conceptual_definition and "cloud services" in _norm(best.get("title")) and "cloud services" not in request_norm
        direct_title = best_fit["title_hit_count"] >= 2
        direct_content = best_fit["covered_count"] >= 2 and best_fit["coverage"] >= 0.4
        semantic_support = best_fit["semantic_score"] >= 0.15
        # Two independent lexical anchors plus target compatibility are enough for
        # exact operational documents even when OCR lowers the semantic score.
        semantic_rejected=bool((out.get("semantic_fit") or {}).get("low_fit")) and float((out.get("semantic_fit") or {}).get("combined_quality",0) or 0) < 0.12
        accepted = target_ok and definition_supported and not unrequested_subservice and not semantic_rejected and (direct_title or (direct_content and semantic_support))
        if accepted:
            identity = _identity(best)
            selected = [item for fit, item in scored if _identity(item) == identity][:8]
            full = best_fit["coverage"] >= 0.5 or best_fit["title_hit_count"] >= 2
            status = "sufficient" if full else "partial"
            mode = "documented" if full else "documented_partial"
            reason = "direct_title_operation_match" if direct_title else "direct_content_and_operation_match"

    for idx, item in enumerate(selected, 1):
        item["id"] = f"R{idx}"
    verdict = {
        "schema_version": 3,
        "status": status,
        "mode": mode,
        "accepted": accepted,
        "reason": reason,
        "request_terms": sorted(wanted),
        "document_ids": list(dict.fromkeys(_identity(x) for x in selected)),
        "evidence_ids": [x["id"] for x in selected],
        "coverage": round(float(best_fit.get("coverage", 0) if best else 0), 4),
        "selected_evidence": deepcopy(selected),
        "rejected_count": max(0, len(candidates) - len(selected)),
    }
    out["evidence_verdict"] = verdict
    out["generation_evidence"] = deepcopy(selected)
    out["evidence"] = deepcopy(selected)
    semantic_fit = out.setdefault("semantic_fit", {})
    semantic_fit.update({
        "accepted_for_generation": accepted,
        "low_fit": not accepted,
        "generation_ids": verdict["evidence_ids"],
        "generation_count": len(selected),
        "selected_document": verdict["document_ids"][0] if verdict["document_ids"] else None,
        "decision_path": "unified_evidence_authority_v3",
    })
    return out
