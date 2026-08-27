from __future__ import annotations
import json
import streamlit as st
st.set_page_config(page_title="Contextual RAG",page_icon="🧩",layout="wide")
st.title("Agent Core v1 - Integración contextual")
st.caption("Puerta de suficiencia técnica, intención troubleshooting y observabilidad del RAG heredado.")
try: debug=bool(st.secrets.get("DEBUG_UI",False))
except Exception: debug=False
if not debug: st.warning("Requiere DEBUG_UI=true."); st.stop()
records=list(st.session_state.get("agent_core_contextual_records",[]) or [])
if records:
    latest=records[-1]
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Registros",len(records));c2.metric("Listo para RAG","Sí" if (latest.get("readiness") or {}).get("ready_for_rag") else "No");c3.metric("RAG","Sí" if latest.get("rag_called") else "No");c4.metric("LLM","Sí" if latest.get("llm_called") else "No")
    st.json(latest)
    with st.expander("Historial",expanded=False):st.json(records)
    st.download_button("Descargar reporte",json.dumps(records,ensure_ascii=False,indent=2),file_name="contextual_rag_v2_fix_records.json",mime="application/json",use_container_width=True)
else: st.info("Todavía no hay solicitudes contextuales ejecutadas en esta sesión.")
