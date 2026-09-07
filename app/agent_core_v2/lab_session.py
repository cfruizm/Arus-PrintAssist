from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agent_core_v2.models import ConversationState
from app.agent_core_v2.interpreter import QwenInterpreter
from app.agent_core_v2.entity_resolver import EntityResolver
from app.agent_core_v2.semantic_evidence_pipeline import SemanticEvidencePipeline
from app.agent_core_v2.response import ResponseComposer
from app.agent_core_v2.engine import TurnEngine
from app.agent_core_v2.adaptive_controller import AdaptiveCostRouteController
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway

SESSION_KEY = "agent_core_v2_free_lab"


def _retrieve(query: str, limit: int) -> list[dict[str, Any]]:
    result = retrieve_from_existing_backend(query, limit)
    if not isinstance(result, dict) or not result.get("ok"):
        return []
    return list(result.get("evidence") or [])


def _new_store() -> dict[str, Any]:
    return {
        "state": ConversationState(conversation_id="free-lab"),
        "messages": [],
        "turns": [],
        "errors": [],
        "llm_history_start": None,
    }


def get_store(streamlit_state) -> dict[str, Any]:
    if SESSION_KEY not in streamlit_state:
        streamlit_state[SESSION_KEY] = _new_store()
    return streamlit_state[SESSION_KEY]


def reset_store(streamlit_state) -> dict[str, Any]:
    streamlit_state[SESSION_KEY] = _new_store()
    return streamlit_state[SESSION_KEY]


def build_engine(secrets, streamlit_state) -> TurnEngine:
    gateway = LLMGateway(load_gateway_config(secrets), streamlit_state)
    route = AdaptiveCostRouteController(
        int(secrets.get("AGENT_CORE_V2_INITIAL_CANDIDATES", 3)),
        int(secrets.get("AGENT_CORE_V2_MAX_CANDIDATES", 6)),
    )
    evidence = SemanticEvidencePipeline(
        _retrieve,
        gateway,
        route.max_candidates,
        int(secrets.get("LLM_EVIDENCE_JUDGE_MAX_TOKENS", 300)),
    )
    return TurnEngine(
        QwenInterpreter(gateway, int(secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS", 240))),
        evidence,
        ResponseComposer(gateway, int(secrets.get("LLM_ANSWER_MAX_TOKENS", 400))),
        EntityResolver(),
        route,
    )


def process_message(message: str, secrets, streamlit_state) -> dict[str, Any]:
    store = get_store(streamlit_state)
    text = " ".join(str(message or "").split())
    if not text:
        raise ValueError("El mensaje no puede estar vacío.")
    engine = build_engine(secrets, streamlit_state)
    try:
        result = engine.process_turn(text, store["state"]).to_dict()
        answer = str((result.get("answer") or {}).get("text") or "").strip()
        if not answer:
            answer = "Registré el turno, pero el laboratorio no produjo una respuesta visible. Revisa el diagnóstico técnico de este turno."
        store["messages"].append({"role": "user", "content": text})
        store["messages"].append({"role": "assistant", "content": answer})
        store["turns"].append(result)
        return result
    except Exception as exc:
        error = {"message": text, "type": type(exc).__name__, "detail": str(exc)}
        store["errors"].append(error)
        raise


def request_escalation(secrets, streamlit_state) -> dict[str, Any]:
    # The request enters through the same canonical V2 engine and shared state.
    # No parallel escalation state or summary implementation is created here.
    return process_message(
        "Quiero escalar el incidente actual con la información recopilada.",
        secrets,
        streamlit_state,
    )


def cancel_current_flow(secrets, streamlit_state) -> dict[str, Any]:
    # Uses the canonical conversational engine so cancellation follows its state transitions.
    return process_message(
        "Cancela la gestión de escalamiento actual y conserva disponible una nueva conversación.",
        secrets,
        streamlit_state,
    )


def public_state(store: dict[str, Any]) -> dict[str, Any]:
    state = store["state"]
    return deepcopy(state.to_dict())


def export_session(streamlit_state) -> dict[str, Any]:
    store = get_store(streamlit_state)
    return {
        "format": "agent_core_v2_free_lab_session",
        "messages": deepcopy(store["messages"]),
        "turns": deepcopy(store["turns"]),
        "state": public_state(store),
        "errors": deepcopy(store["errors"]),
        "production_changed": False,
    }
