from __future__ import annotations
import html
import json
import re
import time
from urllib.parse import urlparse

from app.agent_core.response_evidence_policy import (
    build_response_contract,
    evaluate_document_support,
)
from app.llm_gateway.models import LLMRequest

SENSITIVE_PATTERNS = (
    r"\bfirmware\b",
    r"\bregistro\s+de\s+windows\b",
    r"\bbase\s+de\s+datos\b",
    r"\bfirewall\b",
    r"\bcertificad[oa]s?\b",
    r"\bcredenciales?\b",
    r"\blicencias?\b",
    r"\bgarant[ií]a\b",
    r"\brma\b",
    r"\bfacturaci[oó]n\b",
    r"\beliminar\s+cola\b",
    r"\bmodificar\s+servicios?\b",
    r"\bconfiguraci[oó]n\s+de\s+red\b",
)

FORBIDDEN_UNDOCUMENTED = (
    "reinicia el servicio",
    "reiniciar el servicio",
    "desactiva",
    "desactivar temporalmente",
    "ping ",
    "traceroute",
    "firewall",
    "registro de windows",
    "base de datos",
    "paper-cut-mf.log",
    "papercut-mf.log",
    "snmp poll",
)

# Concept groups are transversal. They represent evidence and support concepts,
# not products or fixed troubleshooting answers.
MULTILINGUAL_CONCEPTS = {
    "time": (
        "fecha", "hora", "momento", "tiempo", "date", "time", "timestamp",
        "interval", "intervalo", "wait time", "waiting time", "timeout",
    ),
    "document": (
        "documento", "archivo", "trabajo", "document", "file", "job",
        "document name", "job name",
    ),
    "capture": (
        "captura", "pantallazo", "imagen", "screenshot", "screen capture",
    ),
    "observation": (
        "observado", "observación", "comportamiento", "observed",
        "observation", "what was observed", "behavior", "behaviour",
    ),
    "expectation": (
        "esperado", "resultado esperado", "expected", "what was expected",
        "expected result",
    ),
    "record": (
        "registrar", "registro", "evidencia", "recopilar", "recolectar",
        "record", "records", "evidence", "collect", "capture", "log", "logs",
    ),
    "user": (
        "usuario", "usuarios", "user", "users", "account",
    ),
    "queue": (
        "cola", "colas", "queue", "queues", "print queue",
    ),
    "processing": (
        "procesar", "procesamiento", "preparación", "preparar", "demora",
        "lento", "tarda", "processing", "preparing", "rendering", "slow",
        "delay", "taking longer",
    ),
    "error": (
        "error", "falla", "fallo", "mensaje", "failed", "failure",
        "status", "estado", "timed out",
    ),
}

TOPIC_GROUPS = {
    "web_print": ("web print", "web-print", "webprint"),
    "scanning": ("scan", "scanning", "scanner", "ocr", "escaneo", "escanear"),
    "mobile_print": ("mobile print", "mobile-print", "movilidad", "impresión móvil"),
    "find_me": ("find-me", "find me", "virtual queue", "cola virtual"),
}


def _plain(value) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_url(value) -> str:
    raw = html.unescape(str(value or "")).strip()
    match = re.search(r"https?://[^\s\"'<>]+", raw)
    if match:
        return match.group(0).rstrip(".,;)")
    if raw.startswith("/"):
        return raw
    return ""


def _tokens(text):
    return set(re.findall(r"[a-záéíóúñ0-9]{3,}", _plain(text).casefold()))


def _overlap(query, text):
    query_tokens = _tokens(query)
    text_tokens = _tokens(text)
    return 0.0 if not query_tokens else len(query_tokens & text_tokens) / len(query_tokens)


def _concepts(text):
    normalized = _plain(text).casefold()
    return {
        concept
        for concept, aliases in MULTILINGUAL_CONCEPTS.items()
        if any(alias in normalized for alias in aliases)
    }


def _topics(text):
    normalized = _plain(text).casefold()
    return {
        topic
        for topic, aliases in TOPIC_GROUPS.items()
        if any(alias in normalized for alias in aliases)
    }


def is_sensitive_query(query):
    normalized = _plain(query).casefold()
    return any(re.search(pattern, normalized) for pattern in SENSITIVE_PATTERNS)


def _clean_item(item):
    cleaned = dict(item or {})
    metadata = dict(cleaned.get("metadata") or {})
    title = _plain(cleaned.get("title") or metadata.get("title"))
    url = _clean_url(
        cleaned.get("url")
        or metadata.get("source_url")
        or metadata.get("canonical_url")
        or cleaned.get("source")
        or metadata.get("source")
    )
    source = _clean_url(cleaned.get("source") or metadata.get("source")) or url
    metadata["title"] = _plain(metadata.get("title") or title)
    for key in ("source", "source_url", "canonical_url"):
        if metadata.get(key):
            metadata[key] = _clean_url(metadata.get(key)) or _plain(metadata.get(key))
    cleaned.update(
        {
            "text": _plain(cleaned.get("text")),
            "title": title,
            "source": source,
            "url": url,
            "metadata": metadata,
        }
    )
    return cleaned


def _canonical(item):
    return (
        _clean_url(item.get("url"))
        or _clean_url(item.get("source"))
        or _plain(item.get("title")).casefold()
    )


def _content_hash(item):
    return str((item.get("metadata") or {}).get("content_hash") or "").strip()


def _topic_penalty(query, item):
    query_topics = _topics(query)
    doc_text = " ".join(
        [item.get("title", ""), item.get("url", ""), item.get("text", "")[:1200]]
    )
    doc_topics = _topics(doc_text)
    if "web_print" in query_topics and "scanning" in doc_topics and "web_print" not in doc_topics:
        return 1.5
    if "web_print" in query_topics and "mobile_print" in doc_topics and "web_print" not in doc_topics:
        return 1.0
    if query_topics and doc_topics and not (query_topics & doc_topics):
        return 0.6
    return 0.0


def _semantic_alignment(query, text):
    query_concepts = _concepts(query)
    text_concepts = _concepts(text)
    if not query_concepts:
        return 0.0
    return len(query_concepts & text_concepts) / len(query_concepts)


def select_evidence(query, evidence, limit=3):
    seen_hash = set()
    seen_identity = set()
    ranked = []
    query_tokens = _tokens(query)
    query_topics = _topics(query)

    for raw_item in evidence or []:
        item = _clean_item(raw_item)
        identity = _canonical(item)
        content_hash = _content_hash(item)
        if (content_hash and content_hash in seen_hash) or (identity and identity in seen_identity):
            continue
        if content_hash:
            seen_hash.add(content_hash)
        if identity:
            seen_identity.add(identity)

        title_text = f"{item.get('title', '')} {item.get('url', '')}"
        full_text = f"{title_text} {item.get('text', '')}"
        lexical = len(query_tokens & _tokens(full_text)) / max(1, len(query_tokens))
        title_overlap = len(query_tokens & _tokens(title_text)) / max(1, len(query_tokens))
        semantic = _semantic_alignment(query, full_text)
        topic_match = 1.0 if query_topics and query_topics & _topics(full_text) else 0.0
        score = lexical + (1.4 * title_overlap) + (1.6 * semantic) + topic_match
        score -= _topic_penalty(query, item)

        ranked.append((score, item, {"lexical": lexical, "semantic": semantic, "topic": topic_match}))

    ranked.sort(key=lambda row: row[0], reverse=True)
    selected = []
    for score, item, detail in ranked:
        if score <= 0:
            continue
        item["selection_score"] = round(score, 4)
        item["selection_detail"] = {key: round(value, 4) for key, value in detail.items()}
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def assess_evidence(query, product, intent, evidence):
    selected = select_evidence(query, evidence, 3)
    if not selected:
        return {
            "identity_score": 0.0,
            "intent_alignment": 0.0,
            "coverage_score": 0.0,
            "source_quality": "none",
            "contradictions": False,
            "sensitive": is_sensitive_query(query),
            "selected_evidence_count": 0,
            "lexical_alignment": 0.0,
            "multilingual_concept_alignment": 0.0,
        }

    combined = " ".join(
        f"{item.get('title', '')} {item.get('url', '')} {item.get('text', '')}"
        for item in selected
    )
    identity = 1.0 if product and product.casefold() in combined.casefold() else (0.5 if not product else 0.2)
    lexical = _overlap(query, combined)
    semantic = _semantic_alignment(query, combined)
    topic = 1.0 if _topics(query) and _topics(query) & _topics(combined) else 0.0
    alignment = min(1.0, max(lexical * 2.0, semantic * 0.85 + topic * 0.15))
    coverage = min(1.0, max(lexical * 1.6, semantic * 0.75 + topic * 0.15))
    official = any(
        "papercut.com" in item.get("url", "")
        or "hp.com" in item.get("url", "")
        or "epson" in item.get("url", "").casefold()
        for item in selected
    )
    return {
        "identity_score": round(identity, 3),
        "intent_alignment": round(alignment, 3),
        "coverage_score": round(coverage, 3),
        "source_quality": "official" if official else "internal_or_unknown",
        "contradictions": False,
        "sensitive": is_sensitive_query(query),
        "selected_evidence_count": len(selected),
        "lexical_alignment": round(lexical, 3),
        "multilingual_concept_alignment": round(semantic, 3),
        "topic_alignment": round(topic, 3),
    }


def deterministic_escalation_answer(query, case_state):
    product = ", ".join(case_state.get("products") or []) or "producto no confirmado"
    symptom = ", ".join(case_state.get("symptoms") or []) or query
    failed = ", ".join(case_state.get("failed_actions") or []) or "ninguna acción documentada"
    return f"""### Cobertura documental
La documentación recuperada corresponde a {product}, pero no permite indicar un procedimiento confiable para este escenario.

### Evidencia por recopilar
- Usuario y equipo afectados.
- Impresora o cola utilizada.
- Hora aproximada del evento.
- Estado visible y mensaje exacto, si existe.
- Acción ya realizada: {failed}.

### Escalamiento recomendado
Evita modificar servicios, red o configuración sin una fuente aplicable. Si el caso persiste, escala adjuntando la evidencia anterior y describiendo: {symptom}."""


def deterministic_mode_fallback(query, case_state, mode):
    if mode == "internal_general":
        return """### Cobertura documental
La documentación disponible no cubre completamente este concepto.

### Orientación general complementaria
La consulta requiere una explicación general, no un procedimiento técnico. Valida la definición específica con la documentación del producto antes de aplicarla a una arquitectura real.

### Validación o escalamiento
Si necesitas configuración o compatibilidad concreta, identifica el producto y consulta su documentación técnica."""
    if mode == "hybrid":
        return deterministic_escalation_answer(query, case_state)
    return deterministic_escalation_answer(query, case_state)


def build_answer_messages(query, case_state, evidence, decision, contract):
    docs = []
    for index, item in enumerate(evidence, 1):
        docs.append(
            {
                "id": f"S{index}",
                "title": item.get("title"),
                "url": item.get("url"),
                "text": str(item.get("text", ""))[:3000],
            }
        )
    system = """Eres el modelo de respuesta técnica de Arus PrintAssist. Sigue exactamente el contrato de evidencia. Responde en español, máximo 220 palabras y máximo cuatro puntos. Termina la respuesta. En modo documented usa solo las fuentes entregadas y cita cada punto con [S1], [S2] o [S3]. Incluye al final 'Fuentes' con IDs y títulos. En modo hybrid separa: Información respaldada por documentación, Cobertura documental, Orientación general complementaria, Validación o escalamiento y Fuentes. Cita solo la sección documentada. No inventes procedimientos ni repitas acciones fallidas. En internal_general no cites fuentes para el conocimiento del modelo."""
    payload = {
        "query": query,
        "case_state": case_state,
        "evidence_decision": decision,
        "response_contract": contract,
        "sources": docs,
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def validate_answer(answer, result, decision, valid_ids):
    violations = []
    lower = str(answer or "").casefold()
    mode = decision.get("response_mode")
    if result.get("finish_reason") == "length":
        violations.append("answer_truncated")
    if mode in {"documented", "hybrid"}:
        used = set(re.findall(r"\[(S\d+)\]", str(answer or "")))
        if not used:
            violations.append("missing_source_ids")
        if used - set(valid_ids):
            violations.append("unknown_source_ids")
        if "documentación oficial" in lower or "documentacion oficial" in lower:
            violations.append("generic_official_source_claim")
    if mode in {"internal_general", "escalate"}:
        for term in FORBIDDEN_UNDOCUMENTED:
            if term in lower:
                violations.append(f"forbidden_undocumented_instruction:{term.strip()}")
    if decision.get("disclosure_required") and "documentación" not in lower:
        violations.append("missing_documentation_disclosure")
    return {"compliant": not violations, "violations": violations}


def run_hybrid_response_lab(
    gateway,
    retrieval_result,
    query,
    case_state,
    intent,
    policy,
    max_tokens=400,
):
    started = time.perf_counter()
    all_evidence = retrieval_result.get("evidence") or []
    evidence = select_evidence(query, all_evidence, 3)
    product = (case_state.get("products") or [""])[0]
    metrics = assess_evidence(query, product, intent, evidence)
    decision = evaluate_document_support(metrics, policy, intent)
    contract = build_response_contract(decision)
    selection = {
        "input_count": len(all_evidence),
        "selected_count": len(evidence),
        "selected_sources": [
            {
                "id": f"S{index}",
                "title": item.get("title"),
                "url": item.get("url"),
                "selection_score": item.get("selection_score"),
                "selection_detail": item.get("selection_detail"),
            }
            for index, item in enumerate(evidence, 1)
        ],
    }

    if decision.response_mode == "escalate":
        answer = deterministic_escalation_answer(query, case_state)
        answer_result = {
            "ok": True,
            "text": answer,
            "provider": "deterministic_policy",
            "model": None,
            "purpose": "technical_answer_guardrail",
            "latency_ms": 0,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "finish_reason": "stop",
            "error_code": None,
            "error_message": None,
            "fallback_used": False,
            "fallback_provider": None,
            "metadata": {"llm_skipped": True, "reason": "policy_escalation"},
        }
    else:
        raw = gateway.complete(
            LLMRequest(
                build_answer_messages(query, case_state, evidence, decision.to_dict(), contract),
                "technical_answer",
                max(250, min(500, max_tokens)),
                0.0,
                None,
            )
        )
        answer_result = raw.to_dict()
        answer = answer_result.get("text", "")

    valid_ids = {f"S{index}" for index in range(1, len(evidence) + 1)}
    compliance = validate_answer(answer, answer_result, decision.to_dict(), valid_ids)
    if not compliance["compliant"]:
        replacement = deterministic_mode_fallback(query, case_state, decision.response_mode)
        answer_result = {
            **answer_result,
            "original_text": answer_result.get("text", ""),
            "text": replacement,
            "guardrail_replaced": True,
        }

    return {
        "query": query,
        "intent": intent,
        "retrieval": retrieval_result,
        "evidence_selection": selection,
        "support_metrics": metrics,
        "evidence_decision": decision.to_dict(),
        "response_contract": contract,
        "answer_result": answer_result,
        "compliance": compliance,
        "total_latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "production_response_changed": False,
    }
