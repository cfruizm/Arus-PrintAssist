from __future__ import annotations
from dataclasses import asdict
import json
import streamlit as st
st.set_page_config(page_title="Contextual RAG",page_icon="🧩",layout="wide")
st.title("Agent Core v1 - Integración contextual")
st.caption("Observabilidad de solicitudes contextuales y consultas enviadas al RAG heredado.")
try: debug=bool(st.secrets.get("DEBUG_UI",False))
except Exception: debug=False
if not debug: st.warning("Requiere DEBUG_UI=true."); st.stop()
records=list(st.session_state.get("agent_core_contextual_records",[]) or [])
if records:
    st.metric("Solicitudes contextuales",len(records)); st.json(records[-1])
    with st.expander("Historial",expanded=False): st.json(records)
    st.download_button("Descargar reporte",json.dumps(records,ensure_ascii=False,indent=2),file_name="contextual_rag_records.json",mime="application/json",use_container_width=True)
else: st.info("Todavía no hay solicitudes contextuales ejecutadas en esta sesión.")
