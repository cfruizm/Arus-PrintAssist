from __future__ import annotations
import json
from datetime import datetime, timezone
import streamlit as st

st.set_page_config(page_title="Router Shadow Observability",page_icon="📋",layout="wide")
st.title("Agent Core v1 - Observación del chat real")
st.caption("Decisiones del router en sombra sobre mensajes reales. No cambia respuestas, no llama al LLM y no consulta Chroma.")
try:
    debug=bool(st.secrets.get("DEBUG_UI",False))
    enabled=bool(st.secrets.get("AGENT_CORE_V1_ROUTER_REAL_CHAT_SHADOW_ENABLED",False))
except Exception:
    debug=False;enabled=False
if not debug:st.warning("Requiere DEBUG_UI=true.");st.stop()
if not enabled:st.info("Agrega AGENT_CORE_V1_ROUTER_REAL_CHAT_SHADOW_ENABLED=true en Secrets para observar mensajes reales.");st.stop()
from app.integration.router_real_chat_shadow import summarize_shadow_records
records=list(st.session_state.get("agent_core_router_shadow_records",[]) or [])
summary=summarize_shadow_records(records)
c1,c2,c3,c4=st.columns(4)
c1.metric("Turnos observados",summary["record_count"])
c2.metric("Errores",summary["error_count"])
c3.metric("LLM",summary["llm_calls"])
c4.metric("Retrieval",summary["retrieval_calls"])
st.subheader("Rutas observadas")
st.json(summary["route_counts"])
if records:
    st.subheader("Último turno")
    st.json(records[-1])
    with st.expander("Historial completo",expanded=False):st.json(records)
    payload=json.dumps({"summary":summary,"records":records},ensure_ascii=False,indent=2)
    st.download_button("Descargar observación JSON",payload,file_name=f"stage5b_real_chat_shadow_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",mime="application/json",use_container_width=True)
else:
    st.info("Todavía no hay turnos observados. Usa el chat principal después de activar el flag.")
if st.button("Limpiar observación de esta sesión",use_container_width=True):
    st.session_state["agent_core_router_shadow_records"]=[]
    st.session_state.pop("agent_core_router_shadow_last_record",None)
    st.rerun()
