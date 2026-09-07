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
st.caption("Laboratorio conversacional libre conectado exclusivamente a app.agent_core_v2. No modifica el chat productivo.")

try:
    enabled = bool(st.secrets.get("AGENT_CORE_LAB_ENABLED", False))
except Exception:
    enabled = False

if not enabled:
    st.info("Agrega AGENT_CORE_LAB_ENABLED = true en Secrets para habilitar el laboratorio.")
    st.stop()

store = get_store(st.session_state)

with st.sidebar:
    st.subheader("Controles")
    if st.button("Nueva conversación", use_container_width=True):
        reset_store(st.session_state)
        st.rerun()

    if st.button("Solicitar escalamiento", use_container_width=True):
        try:
            with st.spinner("Solicitando escalamiento mediante Agent Core v2..."):
                request_escalation(st.secrets, st.session_state)
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo procesar el escalamiento: {type(exc).__name__}: {exc}")

    if st.button("Cancelar flujo actual", use_container_width=True):
        try:
            with st.spinner("Procesando cancelación..."):
                cancel_current_flow(st.secrets, st.session_state)
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo procesar la cancelación: {type(exc).__name__}: {exc}")

    payload = json.dumps(export_session(st.session_state), ensure_ascii=False, indent=2)
    st.download_button(
        "Descargar sesión JSON",
        payload,
        file_name="agent_core_v2_free_lab_session.json",
        mime="application/json",
        use_container_width=True,
    )

    st.divider()
    st.subheader("Estado canónico")
    state = public_state(store)
    topic = state.get("active_topic") or {}
    case = state.get("technical_case") or {}
    escalation = state.get("escalation") or {}

    st.write("**Turno:**", state.get("turn_number", 0))
    st.write("**Tema:**", topic.get("topic_id", "Sin tema"))
    st.write("**Productos:**", ", ".join(x.get("canonical_name") or x.get("matched_text") or x.get("canonical_id", "") for x in topic.get("products") or []) or "No identificados")
    st.write("**Síntomas:**", "; ".join(case.get("symptoms") or []) or "No registrados")
    st.write("**Alcance:**", case.get("affected_scope") or "No registrado")
    attempts = case.get("attempts") or []
    st.write("**Intentos:**", len(attempts))
    st.write("**Estado del caso:**", case.get("status") or "idle")
    st.write("**Escalamiento:**", escalation.get("status") or "inactive")
    if escalation.get("pending_field"):
        st.write("**Campo pendiente:**", escalation.get("pending_field"))

st.subheader("Conversación")
if not store["messages"]:
    st.info("Escribe un caso real con tus propias palabras. No hay escenarios ni productos preconfigurados.")

for item in store["messages"]:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])

prompt = st.chat_input("Escribe tu mensaje de soporte")
if prompt:
    try:
        with st.spinner("Procesando con Agent Core v2..."):
            process_message(prompt, st.secrets, st.session_state)
        st.rerun()
    except Exception as exc:
        st.error(f"Error del laboratorio: {type(exc).__name__}: {exc}")

with st.expander("Diagnóstico técnico", expanded=False):
    if not store["turns"]:
        st.caption("El diagnóstico aparecerá después del primer turno.")
    else:
        for index, turn in enumerate(reversed(store["turns"]), 1):
            turn_number = len(store["turns"]) - index + 1
            st.markdown(f"### Turno {turn_number}")
            st.markdown("**Decisión o propuesta**")
            st.json(turn.get("decision") or turn.get("proposal") or {})
            st.markdown("**Consulta contextual**")
            st.json(turn.get("retrieval_query_trace") or {})
            st.markdown("**Evidencia**")
            evidence = turn.get("evidence") or {}
            st.json({
                "counts": evidence.get("counts") or {},
                "coverage": evidence.get("coverage") or {},
                "citable": evidence.get("citable") or [],
                "contextual": evidence.get("contextual") or [],
            })
            st.markdown("**Respuesta y política**")
            st.json(turn.get("answer") or {})
            st.markdown("**Costo y ruta**")
            st.json(turn.get("cost_route_metrics") or {})
            st.divider()

if store["errors"]:
    with st.expander("Errores de la sesión", expanded=True):
        st.json(store["errors"])
