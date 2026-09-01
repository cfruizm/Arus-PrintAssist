from __future__ import annotations

import time
from typing import Any

from app.agent_core.conversation_act_runtime import compact_case_state
from app.agent_core.hybrid_response_lab import run_hybrid_response_lab
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway


TECHNICAL_CASE_ACTS = {
    "provide_case_detail",
    "report_failed_attempt",
    "report_failed_attempt_and_request_next_step",
    "request_next_step",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _state(chat_session_state) -> dict:
    return compact_case_state(get_or_create_router_shadow_state(chat_session_state))


def _last(values: list[str] | None, default: str = "") -> str:
    clean = [_text(value) for value in (values or []) if _text(value)]
    return clean[-1] if clean else default


def _initial_case_response(state: dict) -> str:
    product = _last(state.get("products"), "el producto indicado")
    symptom = _last(state.get("symptoms"), "el síntoma informado")
    return (
        f"Entiendo el caso en {product}: {symptom}. "
        "Para orientar la validación correcta, necesito ubicar en qué punto deja de verse el trabajo: "
        "¿desaparece de la cola de impresión, del registro del producto o de la pantalla de liberación del dispositivo?"
    )


def _attempt_result_question(state: dict) -> str:
    action = _last(state.get("attempted_actions"), "la validación indicada")
    return (
        f"Entendido. Registré que ya realizaste: {action}. "
        "¿Después de esa validación el problema se resolvió o continúa igual?"
    )


def _safe_contextual_limit(state: dict) -> str:
    product = ", ".join(state.get("products") or []) or "el producto indicado"
    failed = ", ".join(state.get("failed_actions") or [])
    failed_note = f" No repetiré la acción que ya falló: {failed}." if failed else ""
    return (
        f"La documentación recuperada no permite indicar todavía un procedimiento confiable para {product}."
        f"{failed_note} Para continuar, necesito identificar en qué etapa deja de verse el trabajo: "
        "en la cola de impresión, en el registro del producto o en la pantalla de liberación."
    )


def _build_contextual_query(user_message: str, decision: dict, state: dict) -> str:
    request = decision.get("retrieval_request") or {}
    products = list(request.get("products") or state.get("products") or [])
    symptoms = list(state.get("symptoms") or [])
    failed = list(request.get("exclude_actions") or state.get("failed_actions") or [])
    problem = _text(request.get("problem_statement")) or "; ".join(symptoms)
    question = _text(request.get("question")) or _text(user_message)

    parts: list[str] = []
    if products:
        parts.append("Producto: " + ", ".join(products))
    if problem:
        parts.append("Problema: " + problem)
    if failed:
        parts.append("No repetir estas acciones porque ya fallaron: " + "; ".join(failed))
    parts.append(question)
    return ". ".join(part for part in parts if part)


def _retrieve_and_answer(
    user_message: str,
    decision: dict,
    derived: dict,
    state: dict,
    streamlit_state,
    secrets,
) -> tuple[str, dict]:
    query = _build_contextual_query(user_message, decision, state)
    retrieval = retrieve_from_existing_backend(query, 6)
    detail = {
        "query": query,
        "retrieval": retrieval,
        "retrieval_executed": bool(retrieval.get("ok")),
        "answer_llm_called": False,
    }
    if not retrieval.get("ok"):
        detail.update(status="served_guarded", reason="retrieval_failed")
        return _safe_contextual_limit(state), detail

    gateway = LLMGateway(load_gateway_config(secrets), streamlit_state)
    proposal = run_hybrid_response_lab(
        gateway,
        retrieval,
        query,
        state,
        str(derived.get("intent") or "troubleshooting"),
        str(secrets.get("LLM_INTERNAL_KNOWLEDGE_POLICY", "hybrid_guarded")),
        int(secrets.get("LLM_ANSWER_MAX_TOKENS", 400)),
    )
    detail["proposal"] = proposal
    provider = proposal.get("answer_result", {}).get("provider")
    detail["answer_llm_called"] = provider not in {None, "deterministic_policy"}

    answer = _text(proposal.get("answer_result", {}).get("text"))
    compliant = bool(proposal.get("compliance", {}).get("compliant"))
    if not answer or not compliant:
        detail.update(status="served_guarded", reason="proposal_empty_or_non_compliant")
        return _safe_contextual_limit(state), detail

    detail["status"] = "served"
    return proposal.get("answer_result", {}).get("text", "").strip(), detail


def try_semantic_contextual_bridge(
    user_message,
    chat_session_state,
    streamlit_state,
    secrets,
    semantic_record,
):
    """Control visible technical turns using the already computed semantic decision.

    The function runs before the legacy router. Returning an answer prevents the
    legacy backend from writing the same case fact a second time.
    """
    started = time.perf_counter()
    record = {
        "input": user_message,
        "status": "skipped",
        "answer_visible": False,
        "retrieval_executed": False,
        "answer_llm_called": False,
        "controller": "semantic_contextual_bridge_v3",
    }

    try:
        enabled = bool(
            secrets.get("AGENT_CORE_SEMANTIC_TURN_CONTROLLER_ENABLED", False)
            or secrets.get("AGENT_CORE_SEMANTIC_CONTEXTUAL_BRIDGE_ENABLED", False)
        )
        if not enabled:
            record["reason"] = "disabled"
            return None, record

        if not isinstance(semantic_record, dict) or semantic_record.get("status") != "ok":
            record["reason"] = "semantic_unavailable"
            return None, record

        decision = semantic_record.get("normalized_decision") or {}
        derived = semantic_record.get("derived_decision") or {}
        state = _state(chat_session_state)
        act = _text(decision.get("conversation_act"))
        updates = [item for item in (decision.get("state_updates") or []) if isinstance(item, dict)]
        update_types = {str(item.get("type") or "") for item in updates}

        record.update(
            conversation_act=act,
            derived_decision=derived,
            case_state=state,
        )

        if act not in TECHNICAL_CASE_ACTS and not derived.get("requires_retrieval"):
            record["reason"] = "not_a_technical_case_turn"
            return None, record

        if (
            act == "provide_case_detail"
            and "attempted_action" in update_types
            and "attempt_result" not in update_types
        ):
            answer = _attempt_result_question(state)
            record.update(
                status="served",
                route="ask_attempt_result",
                answer_visible=True,
                answer=answer,
            )
            return answer, record

        if (
            act in {
                "report_failed_attempt",
                "report_failed_attempt_and_request_next_step",
                "request_next_step",
            }
            or derived.get("requires_retrieval")
        ):
            answer, detail = _retrieve_and_answer(
                user_message,
                decision,
                derived,
                state,
                streamlit_state,
                secrets,
            )
            record.update(detail)
            record.update(
                route="retrieve_next_step",
                answer_visible=True,
                answer=answer,
            )
            return answer, record

        if act == "provide_case_detail" and state.get("products") and state.get("symptoms"):
            answer = _initial_case_response(state)
            record.update(
                status="served",
                route="initial_technical_clarification",
                answer_visible=True,
                answer=answer,
            )
            return answer, record

        record["reason"] = "insufficient_case_context"
        return None, record

    except Exception as exc:
        record.update(
            status="fallback",
            reason="controller_exception",
            error=f"{type(exc).__name__}: {exc}",
        )
        return None, record
    finally:
        record["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        streamlit_state["agent_core_semantic_contextual_last_record"] = record
        streamlit_state["agent_core_semantic_turn_controller_last_record"] = record
