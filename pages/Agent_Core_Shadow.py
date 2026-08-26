from __future__ import annotations
from datetime import datetime,timezone
import json,streamlit as st
st.set_page_config(page_title="Agent Core Shadow",page_icon="🔬",layout="wide")
st.title("Agent Core v1 - Retrieval en sombra")
st.caption("Segunda corrección 4B: alcance documental, suficiencia por intención y ranking vectorial por posición.")
try:debug=bool(st.secrets.get("DEBUG_UI",False))
except Exception:debug=False
if not debug:st.warning("Requiere DEBUG_UI=true.");st.stop()
from app.backend import retrieve_context,get_vectorstore,get_vectorstore_metadata_value_counts,classify_query_intent,compute_rerank_score
from app.integration.feature_flags import AGENT_CORE_V1_SHADOW_ENABLED
from app.retrieval.real_shadow_evaluator import evaluate_query
if not AGENT_CORE_V1_SHADOW_ENABLED:st.info("Modo sombra desactivado.");st.stop()
query=st.text_area("Consulta",value="¿Qué hacer si los trabajos desaparecen de la cola en PaperCut MF?",height=90);top_k=st.slider("Top K",3,8,6);repetitions=st.selectbox("Repeticiones",[2,3],index=0)
if st.button("Ejecutar segunda corrección",type="primary",use_container_width=True):
    with st.spinner("Comparando retrievals sin LLM..."):result=evaluate_query(query,retrieve_context,get_vectorstore(),get_vectorstore_metadata_value_counts(),classify_query_intent,compute_rerank_score,top_k,repetitions)
    st.session_state["stage4b_second_fix_result"]=result
result=st.session_state.get("stage4b_second_fix_result")
if result:
    c1,c2,c3,c4=st.columns(4);c1.metric("Top 1 coincide","Sí" if result["metrics"]["top1_match"] else "No");c2.metric("Overlap Top 3",result["metrics"]["top3_overlap"]);c3.metric("Soporte intención","Sí" if result["intent_supported"] else "No");c4.metric("LLM",result["llm_calls"])
    if not result["intent_supported"]:st.warning(result["support_reason"])
    st.json(result);st.download_button("Descargar JSON",json.dumps(result,ensure_ascii=False,indent=2),file_name=f"stage4b_second_fix_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",mime="application/json",use_container_width=True)
