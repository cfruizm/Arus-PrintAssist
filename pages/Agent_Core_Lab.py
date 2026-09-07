from __future__ import annotations

import json
import streamlit as st

from app.agent_core_v2.lab_session import (
    cancel_current_flow,
    export_session,
    get_store,
    process_message,
    public_state,
    request_escalation,
    reset_store,
)

st.set_page_config(page_title="Agent Core Lab", page_icon="🧠", layout="wide")
st.title("Agent Core Lab")
st.caption("Laboratorio aislado de Agent Core v2 con retrieval y Groq reales. No modifica el chat productivo.")

try:
    enabled = bool(st.secrets.get("AGENT_CORE_LAB_ENABLED", False))
except Exception:
    enabled = False

if not enabled:
    st.info("Agrega AGENT_CORE_LAB_ENABLED = true en Secrets para habilitar el laboratorio.")
    st.stop()

store = get_store(st.session_state)

with st.sidebar:
    st.subheader("Sesión de laboratorio")
    st.caption("Las acciones afectan únicamente esta sesión aislada.")
    if st.button("Nueva conversación", use_container_width=True, type="primary"):
        reset_store(st.session_state)
        st.rerun()
    if st.button("Solicitar escalamiento", use_container_width=True):
        try:
            with st.spinner("Preparando escalamiento..."):
                request_escalation(st.secrets, st.session_state)
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo procesar el escalamiento: {type(exc).__name__}: {exc}")
    if st.button("Cancelar flujo actual", use_container_width=True):
        try:
            with st.spinner("Cancelando flujo..."):
                cancel_current_flow(st.secrets, st.session_state)
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo procesar la cancelación: {type(exc).__name__}: {exc}")
    payload = json.dumps(export_session(st.session_state), ensure_ascii=False, indent=2)
    st.download_button("Descargar sesión JSON", payload, file_name="agent_core_v2_lab_session.json", mime="application/json", use_container_width=True)
    st.divider()
    state = public_state(store)
    st.metric("Turnos", state.get("turn_number", 0))
    st.metric("Mensajes", len(store.get("messages", [])))
    st.caption("Producción modificada: no")

conversation_tab, diagnostic_tab = st.tabs(["Conversación", "Diagnóstico técnico"])

with conversation_tab:
    if not store.get("messages"):
        st.info("Inicia una conversación libre. Prueba casos reales, seguimientos, correcciones de contexto y escalamiento.")
    for message in store.get("messages", []):
        role = "assistant" if message.get("role") == "assistant" else "user"
        with st.chat_message(role):
            st.markdown(str(message.get("content") or ""))
            meta = message.get("metadata") or {}
            if role == "assistant" and meta:
                citations = meta.get("citations") or []
                if citations:
                    with st.expander("Fuentes utilizadas"):
                        for citation in citations:
                            st.write(citation)
                if meta.get("knowledge_used"):
                    st.caption("Incluye orientación complementaria no validada como documentación específica del producto.")
    prompt = st.chat_input("Describe el caso o continúa la conversación")
    if prompt:
        try:
            with st.spinner("Analizando el caso, consultando documentación y preparando la respuesta..."):
                process_message(prompt, st.secrets, st.session_state)
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo procesar el mensaje: {type(exc).__name__}: {exc}")

with diagnostic_tab:
    st.caption("Vista de observabilidad del laboratorio. No interviene en la decisión del agente.")
    turns = store.get("turns", [])
    if not turns:
        st.info("El diagnóstico aparecerá después del primer turno.")
    else:
        selected = st.selectbox("Turno", range(len(turns), 0, -1), format_func=lambda value: f"Turno {value}")
        turn = turns[selected - 1]
        decision = turn.get("decision") or {}
        metrics = turn.get("cost_route_metrics") or {}
        evidence = turn.get("evidence") or {}
        answer = turn.get("answer") or {}
        counts = evidence.get("counts") or {}
        usage = answer.get("usage") or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Intención", decision.get("intent") or "-")
        c2.metric("Acción", decision.get("action") or "-")
        c3.metric("Documentos", counts.get("retrieved", 0))
        c4.metric("Fuentes citables", counts.get("citable", 0))
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Retrieval", metrics.get("retrieval_calls", 0))
        c6.metric("Juez", metrics.get("judge_calls", 0))
        c7.metric("Tokens respuesta", usage.get("total_tokens", 0))
        c8.metric("Modelo", answer.get("model") or "-")
        with st.expander("Interpretación y decisión", expanded=True):
            st.json({"proposal": turn.get("proposal"), "decision": decision, "semantic_trace": turn.get("semantic_interpretation_trace")})
        with st.expander("Estado canónico"):
            st.json({"before": turn.get("state_before"), "after": turn.get("state_after"), "audit": turn.get("audit")})
        with st.expander("Consulta contextual"):
            st.json(turn.get("retrieval_query_trace") or {})
        with st.expander("Evidencia y fuentes"):
            st.json(evidence)
        with st.expander("Respuesta y ruta adaptativa"):
            st.json({"answer": answer, "response_directive": turn.get("response_directive"), "cost_route_metrics": metrics})
