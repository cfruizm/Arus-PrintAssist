from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="Agent Core Shadow", page_icon="🔬", layout="wide")
st.title("Agent Core v1 - Retrieval en sombra")
st.caption("Diagnóstico de solo lectura. No genera respuestas y no llama al LLM.")

try:
    debug_ui = bool(st.secrets.get("DEBUG_UI", False))
except Exception:
    debug_ui = False

if not debug_ui:
    st.warning("Esta página requiere DEBUG_UI=true en Streamlit Secrets.")
    st.stop()

from app.backend import retrieve_context
from app.integration.feature_flags import AGENT_CORE_V1_SHADOW_ENABLED
from app.integration.stage4a_status import get_stage4a_status
from app.retrieval.real_shadow_evaluator import evaluate_query

status = get_stage4a_status()
st.subheader("Estado")
st.json(status)

if not AGENT_CORE_V1_SHADOW_ENABLED:
    st.info("El modo sombra está instalado pero desactivado. Agrega AGENT_CORE_V1_SHADOW_ENABLED=true en Streamlit Secrets para ejecutar retrieval comparativo.")
    st.stop()

DEFAULT_QUERY = "¿Qué es PaperCut MF?"
query = st.text_area("Consulta de evaluación", value=DEFAULT_QUERY, height=100)
top_k = st.slider("Top K por ejecución", min_value=3, max_value=10, value=6)

if st.button("Ejecutar comparación", type="primary", use_container_width=True):
    with st.spinner("Ejecutando retrieval heredado y candidato, sin LLM..."):
        result = evaluate_query(query, retrieve_context, top_k=top_k)
    st.session_state["agent_core_shadow_last_result"] = result

result = st.session_state.get("agent_core_shadow_last_result")
if result:
    st.subheader("Resultado")
    col1, col2, col3 = st.columns(3)
    col1.metric("Top 1 coincide", "Sí" if result["metrics"]["top1_match"] else "No")
    col2.metric("Overlap Top 3", result["metrics"]["top3_overlap"])
    col3.metric("Llamadas LLM", result["llm_calls"])
    st.json(result)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    st.download_button(
        "Descargar resultado JSON", data=payload,
        file_name=f"agent_core_shadow_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json", use_container_width=True,
    )
