import json
import streamlit as st
from app.agent_core_v2_clean.lab_session import get_store,reset_store,process_message,export_session
st.set_page_config(page_title="Agent Core V2 Clean Lab",page_icon="🧠",layout="wide")
st.title("Agent Core V2 Clean Lab")
st.caption("Fase 1 aislada: comprensión, memoria y conversación. Retrieval deshabilitado intencionalmente.")
try:enabled=bool(st.secrets.get("AGENT_CORE_V2_CLEAN_LAB_ENABLED",False))
except Exception:enabled=False
if not enabled:
 st.info("Agrega AGENT_CORE_V2_CLEAN_LAB_ENABLED = true en Secrets.");st.stop()
store=get_store(st.session_state)
with st.sidebar:
 st.subheader("Laboratorio aislado")
 if st.button("Nueva conversación",use_container_width=True,type="primary"):reset_store(st.session_state);st.rerun()
 payload=json.dumps(export_session(st.session_state),ensure_ascii=False,indent=2)
 st.download_button("Descargar JSON",payload,"agent_core_v2_clean_lab_session.json","application/json",use_container_width=True)
 st.caption("No usa retrieval, V1, V2 anterior ni producción.")
with st.expander("Estado interno",expanded=False):st.json(store["memory"].to_dict())
for m in store["messages"]:
 with st.chat_message(m["role"]):st.markdown(m["content"])
if prompt:=st.chat_input("Escribe un mensaje"):
 with st.chat_message("user"):st.markdown(prompt)
 with st.chat_message("assistant"):
  with st.spinner("Procesando..."):
   result=process_message(prompt,st.secrets,st.session_state)
  st.markdown(result.get("answer",{}).get("text") or "No hubo respuesta visible.")
 st.rerun()
