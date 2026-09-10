from __future__ import annotations
import hashlib
import json
import re
import unicodedata
from .models import AgentResponse
from .answer_context_policy import enrich_internal_payload

PROMPT_VERSION = "controlled_internal_knowledge_v13_scope_contract"
WARNING = "⚠️ **Orientación complementaria basada en conocimiento general del modelo**"
SYSTEM = """Actúa como colega de soporte empresarial de impresión. Usa exactamente: ### Lo que indica la documentación, ### Orientación complementaria, ### Antes de continuar. La primera sección solo usa extractos autorizados y citas [R#]. Las otras secciones no usan citas. Responde al objetivo actual. Respeta hechos confirmados. La evidencia describe posibilidades, no elecciones del usuario. No conviertas modalidades sugeridas en hechos. Si una modalidad no está confirmada, usa lenguaje condicional. Da primero comprobaciones comunes y después comprobaciones condicionales. Formula como máximo una pregunta indispensable. No menciones procesos internos. Máximo 220 palabras."""

MAX_AUTHORIZED_ITEMS = 4
MAX_AUTHORIZED_CHARS = 3200
MAX_ITEM_TEXT_CHARS = 900


def _norm(value):
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", str(value or "").casefold())
        if not unicodedata.combining(c)
    )


def _terms(value):
    return set(re.findall(r"[a-z0-9]{3,}", _norm(value)))


def _stable(evidence):
    payload = [
        evidence.get("url") or evidence.get("source"),
        evidence.get("page"),
        " ".join(str(evidence.get("text") or "").split()),
    ]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def authorized_evidence(
    retrieval,
    question="",
    goal="",
    max_items=MAX_AUTHORIZED_ITEMS,
    max_chars=MAX_AUTHORIZED_CHARS,
):
    current = list(retrieval.get("generation_evidence") or retrieval.get("evidence") or [])
    previous = list(((retrieval.get("_answer_context") or {}).get("cited_evidence") or []))
    query_terms = _terms(f"{question} {goal}")
    candidates = []

    for origin, rows in (("current_turn", current), ("previous_answer", previous)):
        for position, evidence in enumerate(rows):
            stable_id = _stable(evidence)
            text = " ".join(str(evidence.get("text") or "").split())
            evidence_terms = _terms(f"{evidence.get('title', '')} {text}")
            overlap = len(query_terms & evidence_terms)
            density = overlap / max(1, len(query_terms))
            current_turn_tie_break = 0.02 if origin == "current_turn" else 0.0
            candidates.append(
                (
                    density + current_turn_tie_break,
                    overlap,
                    -position,
                    origin,
                    evidence,
                    stable_id,
                    text,
                )
            )

    candidates.sort(reverse=True, key=lambda item: (item[0], item[1], item[2]))
    selected = []
    seen = set()
    used_chars = 0

    for _, overlap, _, origin, evidence, stable_id, text in candidates:
        if stable_id in seen:
            continue
        if selected and overlap <= 0:
            continue

        row = {
            "id": f"R{len(selected) + 1}",
            "stable_id": stable_id,
            "title": evidence.get("title"),
            "page": evidence.get("page"),
            "text": text[:MAX_ITEM_TEXT_CHARS],
            "origin": origin,
        }
        row_chars = len(json.dumps(row, ensure_ascii=False))
        if selected and used_chars + row_chars > max_chars:
            continue

        selected.append(row)
        seen.add(stable_id)
        used_chars += row_chars
        if len(selected) >= max_items:
            break

    return selected


def repair_citation_placement(text):
    value = str(text or "")
    names = ["Lo que indica la documentación", "Orientación complementaria", "Antes de continuar"]
    positions = []
    for name in names:
        match = re.search(re.escape(name), value, re.I)
        positions.append(match.start() if match else -1)
    if not (all(position >= 0 for position in positions) and positions == sorted(positions)):
        return value, False
    rest = re.sub(r"\s*\[(R\d+)\]", "", value[positions[1]:])
    return value[:positions[1]] + rest, rest != value[positions[1]:]


def validate_internal(text, finish_reason=None, valid_ids=None):
    value = str(text or "").strip()
    names = ["Lo que indica la documentación", "Orientación complementaria", "Antes de continuar"]
    positions = []
    for name in names:
        match = re.search(re.escape(name), value, re.I)
        positions.append(match.start() if match else -1)
    ordered = all(position >= 0 for position in positions) and positions == sorted(positions)
    complete = str(finish_reason or "").casefold() not in {"length", "max_tokens"}
    first = value[positions[0]:positions[1]] if ordered else ""
    rest = value[positions[1]:] if ordered else value
    documented = set(re.findall(r"\[(R\d+)\]", first))
    internal = set(re.findall(r"\[(R\d+)\]", rest))
    known = set(valid_ids or [])
    safe = bool(value) and ordered and not internal and documented.issubset(known)
    return safe and complete, {
        "safe_partial": safe,
        "sections_present": [name for name, position in zip(names, positions) if position >= 0],
        "separation_valid": ordered,
        "finish_complete": complete,
        "documented_citations": sorted(documented),
        "internal_citations": sorted(internal),
        "unknown_citations": sorted((documented | internal) - known),
    }


def fingerprint(message, understanding, retrieval, assessment, model=""):
    evidence = authorized_evidence(
        retrieval,
        message,
        understanding.get("current_goal") or "",
    )
    payload = {
        "q": " ".join(str(message).split()).casefold(),
        "goal": understanding.get("current_goal"),
        "assessment": assessment.get("status"),
        "evidence": [item.get("stable_id") for item in evidence],
        "model": model,
        "prompt": PROMPT_VERSION,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:24]


class ControlledInternalKnowledgeComposer:
    def __init__(self, gateway, max_tokens=420):
        self.gateway = gateway
        self.max_tokens = max(320, min(520, int(max_tokens)))
        self.last_provider_result = {}
        self.validation = {}
        self.attempts = []

    def compose(self, message, understanding, retrieval, assessment):
        from app.llm_gateway.models import LLMRequest

        evidence = authorized_evidence(
            retrieval,
            message,
            understanding.get("current_goal") or "",
        )
        payload = {
            "question": message,
            "goal": understanding.get("current_goal"),
            "documentation_assessment": assessment,
            "authorized_evidence": evidence,
        }
        payload = enrich_internal_payload(
            payload,
            retrieval.get("_answer_context") or {},
            understanding,
        )
        result = self.gateway.complete(
            LLMRequest(
                [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    },
                ],
                "agent_core_v2_clean_internal_knowledge",
                self.max_tokens,
                0.0,
                None,
            )
        )
        self.attempts = [result.to_dict()]
        valid_ids = [item["id"] for item in evidence]
        valid, diagnostic = validate_internal(
            result.text if result.ok else "",
            result.finish_reason,
            valid_ids,
        )

        if result.ok and not valid and diagnostic.get("separation_valid") and diagnostic.get("finish_complete"):
            repaired, changed = repair_citation_placement(result.text)
            if changed:
                result.text = repaired
                valid, diagnostic = validate_internal(repaired, result.finish_reason, valid_ids)
                diagnostic["deterministic_citation_repair"] = True

        self.validation = {
            **diagnostic,
            "retry_used": False,
            "attempt_count": 1,
            "selected_attempt": 1,
            "published_partial": False,
            "selected_evidence_ids": valid_ids,
            "authorized_stable_ids": [item["stable_id"] for item in evidence],
            "authorized_evidence_count": len(evidence),
            "authorized_evidence_chars": sum(len(item.get("text") or "") for item in evidence),
            "answer_context_used": bool(payload.get("previous_answer_context")),
            "compact_followup_context": bool(payload.get("previous_answer_context")),
        }
        self.last_provider_result = {
            **result.to_dict(),
            "selected_attempt": 1,
            "attempts": self.attempts,
            "aggregate_usage": result.usage,
            "aggregate_latency_ms": float(getattr(result, "latency_ms", 0) or 0),
        }

        if not result.ok:
            return AgentResponse(
                "La documentación no es suficiente y no fue posible generar orientación complementaria.",
                "internal_knowledge_provider_degraded",
                False,
            )
        if not valid:
            return AgentResponse(
                "Encontré orientación relacionada, pero no puedo publicarla sin una separación documental válida.",
                "internal_knowledge_separation_guard",
                False,
                result.provider,
                result.model,
                result.usage,
                result.finish_reason,
            )
        return AgentResponse(
            f"{WARNING}\n\n{str(result.text).strip()}",
            "controlled_internal_knowledge",
            True,
            result.provider,
            result.model,
            result.usage,
            result.finish_reason,
        )
