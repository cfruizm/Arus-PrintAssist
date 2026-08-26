from __future__ import annotations
from datetime import datetime,timezone
import json
import streamlit as st
st.set_page_config(page_title="Agent Core Shadow",page_icon="🔬",layout="wide")
st.title("Agent Core v1 - Retrieval en sombra")
st.caption("Revisión 4B. Consulta original, entidad externa, scoring explicable y cero llamadas al LLM.")
try:debug_ui=bool(st.secrets.get("DEBUG_UI",False))
except Exception:debug_ui=False
if not debug_ui:st.warning("Esta página requiere DEBUG_UI=true.");st.stop()
from app.backend import retrieve_context,get_vectorstore,get_vectorstore_metadata_value_counts,classify_query_intent,compute_rerank_score
from app.integration.feature_flags import AGENT_CORE_V1_SHADOW_ENABLED
from app.retrieval.real_shadow_evaluator import evaluate_query
if not AGENT_CORE_V1_SHADOW_ENABLED:st.info("Modo sombra desactivado.");st.stop()
st.info("Ejecuta primero una sola consulta. El calentamiento se mide aparte y no se incluye en la mediana.")
query=st.text_area("Consulta",value="¿Qué es PaperCut MF?",height=90); top_k=st.slider("Top K",3,8,6); repetitions=st.selectbox("Repeticiones medidas",[2,3],index=0)
if st.button("Ejecutar comparación revisada",type="primary",use_container_width=True):
    with st.spinner("Calentando recursos y comparando retrievals, sin LLM..."):
        result=evaluate_query(query,retrieve_context,get_vectorstore(),get_vectorstore_metadata_value_counts(),classify_query_intent,compute_rerank_score,top_k,repetitions)
    st.session_state["stage4b_revision_result"]=result
result=st.session_state.get("stage4b_revision_result")
if result:
    c1,c2,c3,c4=st.columns(4);c1.metric("Top 1 coincide","Sí" if result["metrics"]["top1_match"] else "No");c2.metric("Overlap Top 3",result["metrics"]["top3_overlap"]);c3.metric("LLM",result["llm_calls"]);c4.metric("Warm-up",result["warmup_seconds"])
    st.json(result)
    st.download_button("Descargar JSON",json.dumps(result,ensure_ascii=False,indent=2),file_name=f"stage4b_revision_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",mime="application/json",use_container_width=True)
