from __future__ import annotations
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from .models import AgentResponse
from .source_footer import compact_sources, strip_generated_source_footer
from .diagnostic_language import soften_diagnostic_certainty
from .guidance_integrity import build_guidance_integrity_contract, integrity_diagnostic

PROMPT_VERSION = "documented_v11_confirmed_action_integrity"
SYSTEM = """Eres un colega de soporte empresarial de impresion. Responde unicamente con la evidencia documental suministrada y usa el idioma del usuario. Se util, directo y natural. No inventes menus, pasos, requisitos, relaciones ni funciones. Cada afirmacion factual debe terminar con una o mas citas [R#].

Ajusta la forma al objetivo:
- conceptual: empieza con una definicion o descripcion directa. Despues explica proposito, capacidades o componentes solamente cuando esten respaldados. No conviertas una definicion en una lista completa de requisitos.
- requirements: sintetiza todas las categorias de condiciones previas respaldadas por el conjunto de evidencia, no solo por el primer fragmento. Separa categorias y conserva alternativas como alternativas.
- procedural: conserva el orden documental y no rellenes pasos ausentes.

Integra fragmentos complementarios del mismo documento y de paginas posteriores. No copies un unico enunciado si otros fragmentos autorizados agregan capacidades materialmente distintas. Si una parte solicitada no aparece, responde primero todo lo que si esta documentado y declara la limitacion de forma localizada. Nunca afirmes ausencia global sin revisar todos los fragmentos. En seguimientos del mismo caso, no vuelvas a definir, presentar ni describir el producto. Empieza por el nuevo hecho confirmado, su implicación y la siguiente comprobación respaldada. Prioriza cobertura completa y concisa sobre detalle secundario. Para una consulta inicial usa como máximo 320 palabras; para un seguimiento del mismo caso usa como máximo 220 palabras. En troubleshooting prioriza la implicación del dato nuevo y hasta tres comprobaciones de mayor valor diagnóstico. No repitas definiciones, contexto, fuentes equivalentes ni recomendaciones ya realizadas. En seguimientos usa máximo 180 palabras y no más de tres comprobaciones numeradas. Continúa primero una comprobación truncada. No repitas acciones incluidas en already_delivered_guidance. Las recomendaciones mostradas anteriormente NO son acciones ejecutadas. Considera realizada una validación únicamente cuando aparezca en user_confirmed_attempts. Nunca uses expresiones de ejecución previa, como afirmar que algo ya fue verificado, basándote solo en assistant_delivered_guidance. Si una acción no está confirmada, mantenla como pendiente y redáctala en futuro o como instrucción. Antes de publicar una acción, evalúa semánticamente su impacto y reversibilidad. Si puede causar pérdida de configuración o datos, interrupción, impacto amplio, cambios de seguridad/acceso o rollback difícil, no la presentes como acción rutinaria ni temprana: indica condición de uso, impacto, prerrequisitos de respaldo/recuperación, autorización o ventana cuando apliquen, y ofrece escalamiento si no puede ejecutarse con seguridad. No declares una causa o capa descartada salvo evidencia explícita. Una validación correcta solo reduce probabilidad; formula la siguiente hipótesis como ampliación del diagnóstico, no como causa confirmada ni exclusión definitiva. No menciones procesos internos del laboratorio."""

_STOP = {
    "cuales", "cual", "especificamente", "requisitos", "requisito", "necesito",
    "identify", "specific", "requirements", "subject", "para", "sobre", "tiene",
    "tienen", "del", "los", "las", "son", "que", "what", "which", "documentado",
    "documentada", "documentacion", "informacion", "explica", "explicar", "define",
}


def _norm(value):
    return " ".join(
        "".join(c for c in unicodedata.normalize("NFKD", str(value or "").casefold()) if not unicodedata.combining(c)).split()
    )


def _terms(value):
    return {
        x for x in re.findall(r"[a-z0-9]+", _norm(value))
        if len(x) >= 4 and x not in _STOP
    }


def _identity(item):
    meta = item.get("metadata") or {}
    return str(item.get("url") or item.get("source") or meta.get("canonical_url") or item.get("title") or "")


def _page_key(item):
    return (_identity(item), str(item.get("page") or (item.get("metadata") or {}).get("page_label") or ""))


def _candidate_rows(retrieval):
    verdict = retrieval.get("evidence_verdict") or {}
    rows = verdict.get("selected_evidence") or retrieval.get("generation_evidence") or retrieval.get("evidence") or []
    out, seen = [], set()
    for row in rows:
        text = " ".join(str(row.get("text") or "").split())
        if len(text) < 40:
            continue
        signature = hashlib.sha256((str(_page_key(row)) + text.casefold()).encode()).hexdigest()
        if signature in seen:
            continue
        seen.add(signature)
        clean = dict(row)
        clean["text"] = text
        out.append(clean)
    return out


def evidence_pack(retrieval, message="", understanding=None, max_items=6, max_chars=6200):
    followup=(str((understanding or {}).get("user_act") or "") in {"follow_up","answer_to_question","request_elaboration","attempt_result","reported_failure"} or str((understanding or {}).get("topic_relation") or "") in {"same_topic","return_to_previous"})
    if followup:max_items,max_chars=min(max_items,4),min(max_chars,4500)
    """Select a diverse, relevance-ordered evidence set without losing later pages."""
    rows = _candidate_rows(retrieval)
    wanted = _terms(" ".join((str(message or ""), str((understanding or {}).get("current_goal") or ""))))
    scored = []
    for position, row in enumerate(rows):
        body_terms = _terms(" ".join((str(row.get("title") or ""), row["text"])))
        overlap = len(wanted & body_terms) / max(1, len(wanted))
        semantic = float((row.get("semantic_fit") or {}).get("score", 0.0) or 0.0)
        scored.append((0.72 * overlap + 0.28 * semantic, -position, row))
    scored.sort(reverse=True, key=lambda value: (value[0], value[1]))

    # First pass preserves page/document diversity. Second pass fills remaining capacity.
    buckets = defaultdict(list)
    for score, position, row in scored:
        buckets[_page_key(row)].append((score, position, row))
    ordered = [values[0] for values in buckets.values()]
    ordered.sort(reverse=True, key=lambda value: (value[0], value[1]))
    selected_ids = {id(value[2]) for value in ordered}
    ordered.extend(value for value in scored if id(value[2]) not in selected_ids)

    items, used = [], 0
    for _, _, row in ordered:
        item = {
            "id": row.get("id"), "title": row.get("title"), "page": row.get("page"),
            "source": row.get("url") or row.get("source"), "text": row["text"][:2200],
        }
        size = len(json.dumps(item, ensure_ascii=False))
        if items and used + size > max_chars:
            continue
        items.append(item)
        used += size
        if len(items) >= max_items:
            break
    return items


def requested_dimensions(message, understanding):
    subject = _terms((understanding or {}).get("canonical_subject") or (understanding or {}).get("goal_updates", {}).get("subject"))
    return sorted(_terms(message) - subject)


def dimension_coverage(message, understanding, evidence):
    terms = requested_dimensions(message, understanding)
    body = _norm(" ".join(str(x.get("text") or "") for x in evidence))
    covered = [x for x in terms if x in body]
    return {"requested": terms, "covered": covered, "missing": [x for x in terms if x not in body], "sufficient": not terms or bool(covered)}


def contradicted_absence(text, message, understanding, evidence):
    body = _norm(text)
    absence = any(x in body for x in (
        "no especifica", "no contiene", "no detalla", "no proporciona", "no documenta",
        "no es posible responder", "not specify", "not contain", "not document",
    ))
    coverage = dimension_coverage(message, understanding, evidence)
    return bool(absence and coverage["covered"]), coverage


def validate_citations(text, ids):
    cited = set(re.findall(r"\[(R\d+)\]", text or ""))
    return bool(str(text or "").strip()) and bool(cited) and cited.issubset(set(ids)), sorted(cited)


def safe_cited_partial(text, valid_ids, finish_reason):
    """Publish only complete cited content when the provider exhausts output.

    This is structural and domain-independent: no products, actions, symptoms,
    or campaign phrases are inspected. The boundary is the final complete
    canonical citation emitted by the documented composer.
    """
    if str(finish_reason or "").casefold() not in {"length", "max_tokens"}:
        return None, []
    value = str(text or "").strip()
    matches = list(re.finditer(r"\[(R\d+)\]", value))
    if not matches:
        return None, []
    allowed = set(map(str, valid_ids or []))
    complete = [m for m in matches if m.group(1) in allowed]
    if not complete:
        return None, []
    cut = complete[-1].end()
    partial = value[:cut].rstrip()
    cited = sorted(set(re.findall(r"\[(R\d+)\]", partial)))
    if not partial or not cited or not set(cited).issubset(allowed):
        return None, []
    return partial, cited


def answer_fingerprint(message, understanding, retrieval, model=""):
    payload = {
        "q": " ".join(str(message).split()).casefold(), "goal": understanding.get("current_goal"),
        "intent": understanding.get("intent"), "retrieval": (retrieval.get("query") or {}).get("fingerprint"),
        "evidence": [(e.get("id"), e.get("url") or e.get("source"), e.get("page")) for e in _candidate_rows(retrieval)],
        "model": model, "prompt": PROMPT_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


def readable_sources(evidence, cited_ids):
    by_id = {str(e.get("id")): e for e in evidence}
    return [f"[{rid}] {by_id[rid].get('title') or 'Fuente sin titulo'}, pagina {by_id[rid].get('page') or 'N/D'}" for rid in cited_ids if rid in by_id]



def _compact_followup_checks(text, understanding, maximum=3):
    followup=(str((understanding or {}).get("user_act") or "") in {"follow_up","answer_to_question","request_elaboration","attempt_result","reported_failure"} or str((understanding or {}).get("topic_relation") or "") in {"same_topic","return_to_previous"})
    if not followup:return text
    matches=list(re.finditer(r"(?m)^\s*(\d+)[.)]\s+",str(text or "")))
    if len(matches)<=maximum:return text
    return str(text or "")[:matches[maximum].start()].rstrip()

class DocumentedAnswerComposer:
    def __init__(self, gateway, max_tokens=360):
        self.gateway = gateway
        self.max_tokens = max(320, min(900, int(max_tokens)))
        self.last_provider_result = {}
        self.validation = {}

    def compose(self, message, understanding, retrieval):
        intent = str(understanding.get("intent") or "").casefold()
        requirements = intent == "requirements"
        conceptual = intent == "conceptual"
        evidence = evidence_pack(
            retrieval, message, understanding,
            max_items=16 if requirements else 12 if conceptual else 8,
            max_chars=16000 if requirements else 12000 if conceptual else 8000,
        )
        if not evidence:
            return AgentResponse("La recuperacion no contiene evidencia suficiente para responder de forma documentada.", "documented_insufficient", False)
        from app.llm_gateway.models import LLMRequest
        previous=dict(retrieval.get("_answer_context") or {})
        followup=(str(understanding.get("user_act") or "") in {"follow_up","answer_to_question","request_elaboration","attempt_result","reported_failure"} or str(understanding.get("topic_relation") or "") in {"same_topic","return_to_previous"})
        integrity_contract=build_guidance_integrity_contract(retrieval)
        payload = {
            "question": message, "intent": intent, "goal": understanding.get("current_goal"),"followup":followup,
            "already_delivered_guidance":list(previous.get("delivered_guidance") or [])[:8],"previous_answer_partial":bool(previous.get("partial")),
            "guidance_integrity_contract":integrity_contract,
            "user_confirmed_attempts":integrity_contract["user_confirmed_attempts"],
            "assistant_delivered_guidance":integrity_contract["assistant_delivered_guidance"],
            "coverage_contract": {
                "use_all_relevant_fragments": not followup,
                "preserve_later_page_information": True,
                "definition_does_not_imply_full_requirements": conceptual,
                "max_numbered_checks":3 if followup else None,
                "required_shape": "definition_purpose_capabilities_if_supported" if conceptual else "requirement_categories" if requirements else "proportional",
            },
            "evidence": evidence,
        }
        limit = 760 if requirements else 620 if conceptual else self.max_tokens
        result = self.gateway.complete(LLMRequest(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
            "agent_core_v2_clean_documented_answer", limit, 0.0, None,
        ))
        self.last_provider_result = result.to_dict()
        if not result.ok:
            return AgentResponse("Encontre documentacion, pero no pude redactar la respuesta en este turno. Las fuentes recuperadas se conservaron.", "documented_provider_degraded", False)
        text = _compact_followup_checks(str(result.text or "").strip(),understanding)
        text,certainty_softened = soften_diagnostic_certainty(text,intent)
        contradiction, dimension_check = contradicted_absence(text, message, understanding, evidence)
        valid_ids = [str(x["id"]) for x in evidence]
        valid, cited = validate_citations(text, valid_ids)
        truncated = str(result.finish_reason or "").casefold() in {"length", "max_tokens"}
        safe_partial_text, safe_partial_cited = safe_cited_partial(text, valid_ids, result.finish_reason)
        safe_partial = bool(truncated and safe_partial_text)
        if safe_partial:
            text = safe_partial_text
            cited = safe_partial_cited
        cited_pages = {str(x.get("page") or "") for x in evidence if str(x.get("id")) in cited and x.get("page") not in (None, "")}
        available_pages = {str(x.get("page") or "") for x in evidence if x.get("page") not in (None, "")}
        required_page_coverage = min(3, len(available_pages)) if requirements else min(2, len(available_pages)) if conceptual else 1
        complete_page_coverage = len(cited_pages) >= required_page_coverage
        partial_page_coverage = safe_partial and bool(cited) and (bool(cited_pages) or not available_pages)
        page_coverage_valid = complete_page_coverage or partial_page_coverage
        valid = bool((valid or safe_partial) and page_coverage_valid and not contradiction)
        self.validation = {
            "citations_valid": valid, "cited_ids": cited, "finish_reason": result.finish_reason,
            "truncated": truncated, "published_partial": bool(valid and safe_partial),
            "safe_partial_terminal": bool(valid and safe_partial),
            "evidence_pages": sorted(available_pages), "cited_pages": sorted(cited_pages),
            "required_page_coverage": required_page_coverage, "page_coverage_valid": page_coverage_valid,
            "requested_dimension_coverage": dimension_check, "contradicted_absence_blocked": contradiction,
            "evidence_items_supplied": len(evidence), "prompt_version": PROMPT_VERSION,
            "diagnostic_certainty_softened": certainty_softened,
            "guidance_integrity": integrity_diagnostic(integrity_contract),
        }
        if contradiction:
            return AgentResponse("La respuesta generada contradecia la evidencia documental recuperada y fue bloqueada antes de publicarse. Intenta nuevamente para regenerar la sintesis documentada.", "documented_evidence_contradiction_guard", False, result.provider, result.model, result.usage, result.finish_reason)
        if not valid:
            return AgentResponse("Encontre documentacion, pero la respuesta generada no cubrio suficientemente la evidencia o no supero la validacion de citas.", "documented_citation_guard", False, result.provider, result.model, result.usage, result.finish_reason)
        text=strip_generated_source_footer(text)
        if safe_partial:
            text += "\n\n> Respuesta parcial segura: el proveedor alcanzó el límite de salida. Se publicó únicamente el contenido completo y citado disponible."
        footer = compact_sources(evidence, cited)
        if footer:text += "\n\n" + footer
        return AgentResponse(text, "documented_answer_partial" if safe_partial else "documented_answer", True, result.provider, result.model, result.usage, "safe_partial" if safe_partial else result.finish_reason)
