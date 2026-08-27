from __future__ import annotations
from dataclasses import asdict
import json
import streamlit as st
st.set_page_config(page_title="Contextual RAG",page_icon="🧩",layout="wide")
st.title("Agent Core v1 - Integración contextual")
st.caption("Previsualiza la consulta contextual sin llamar al RAG ni al LLM.")
try:
    debug=bool(st.secrets.get("DEBUG_UI",False))
except Exception: debug=False
if not debug: st.warning("Requiere DEBUG_UI=true."); st.stop()
from app.integration.contextual_rag_v1 import evaluate_contextual_request
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state
chat_state=st.session_state.get("chat_session_state") or st.session_state.get("session_state")
if chat_state is None:
    st.info("No se encontró una sesión de chat activa en esta página. Usa primero el chat principal.")
    st.stop()
agent_state=get_or_create_router_shadow_state(chat_state)
st.subheader("Estado Agent Core")
st.json(asdict(agent_state))
message=st.text_input("Solicitud de continuación",value="¿Qué puedo hacer ahora?")
if st.button("Construir consulta sin costo",type="primary",use_container_width=True):
    st.session_state["context_preview"]=evaluate_contextual_request(message,chat_state)
if "context_preview" in st.session_state:
    st.json(st.session_state["context_preview"])
    st.download_button("Descargar previsualización",json.dumps(st.session_state["context_preview"],ensure_ascii=False,indent=2),file_name="contextual_query_preview.json",mime="application/json",use_container_width=True)
