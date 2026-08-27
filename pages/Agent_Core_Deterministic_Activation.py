from __future__ import annotations
import json
from datetime import datetime, timezone
import streamlit as st
st.set_page_config(page_title="Deterministic Activation",page_icon="✅",layout="wide")
st.title("Agent Core v1 - Activación determinística")
st.caption("Rutas autorizadas de bajo riesgo y fallbacks al backend heredado.")
try:
    debug=bool(st.secrets.get("DEBUG_UI",False))
    enabled=bool(st.secrets.get("AGENT_CORE_V1_DETERMINISTIC_ENABLED",False))
except Exception:
    debug=False;enabled=False
if not debug:st.warning("Requiere DEBUG_UI=true.");st.stop()
from app.integration.deterministic_activation_v1 import summarize_activation_records
records=list(st.session_state.get("agent_core_deterministic_records",[]) or [])
summary=summarize_activation_records(records)
c1,c2,c3,c4=st.columns(4)
c1.metric("Turnos",summary["record_count"]);c2.metric("Determinísticos",summary["authorized_count"]);c3.metric("Fallback legacy",summary["fallback_count"]);c4.metric("Errores",summary["error_count"])
st.write("**Flag activo:**",enabled)
st.json(summary["route_counts"])
if records:
    st.subheader("Último turno");st.json(records[-1])
    with st.expander("Historial",expanded=False):st.json(records)
    st.download_button("Descargar reporte",json.dumps({"summary":summary,"records":records},ensure_ascii=False,indent=2),file_name=f"deterministic_activation_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",mime="application/json",use_container_width=True)
else:st.info("No hay turnos registrados en esta sesión.")
if st.button("Limpiar registros de esta sesión",use_container_width=True):
    st.session_state["agent_core_deterministic_records"]=[];st.session_state.pop("agent_core_deterministic_last_record",None);st.rerun()
