from __future__ import annotations
import json
import streamlit as st
st.set_page_config(page_title="Semantic Orchestrator",page_icon="🧠",layout="wide")
st.title("Agent Core v1 - Orquestador semántico en sombra")
st.caption("Una llamada LLM interpreta el turno y devuelve JSON estructurado. No cambia el chat ni ejecuta retrieval.")
try:debug=bool(st.secrets.get("DEBUG_UI",False));enabled=bool(st.secrets.get("AGENT_CORE_V1_SEMANTIC_SHADOW_ENABLED",False))
except Exception:debug=False;enabled=False
if not debug:st.warning("Requiere DEBUG_UI=true.");st.stop()
if not enabled:st.info("Agrega AGENT_CORE_V1_SEMANTIC_SHADOW_ENABLED=true en Secrets.");st.stop()
from app.backend import get_hf_client,call_hf_chat_completion,extract_llm_answer_text
from app.agent_core.semantic_orchestrator import evaluate_semantic_turn
from app.integration.semantic_shadow_adapter import build_hf_llm_call
if "semantic_shadow_case" not in st.session_state:st.session_state.semantic_shadow_case={"conversation":{"last_route":None},"topic":{"products":[],"processes":[]},"technical_case":{"status":"idle","symptoms":[],"attempted_actions":[],"failed_actions":[],"affected_users":None,"resolution_status":None,"context_facts":[]},"turn_number":0}
if "semantic_shadow_results" not in st.session_state:st.session_state.semantic_shadow_results=[]
message=st.text_area("Mensaje libre",value="Después de enviarlos ya no veo los documentos.",height=90)
if st.button("Interpretar semánticamente",type="primary",use_container_width=True):
    client=get_hf_client()
    if client is None:st.error("HF_TOKEN no está disponible.")
    else:
        invoke=build_hf_llm_call(client,call_hf_chat_completion,extract_llm_answer_text)
        with st.spinner("Interpretando el turno..."):
            result=evaluate_semantic_turn(message,st.session_state.semantic_shadow_case,st.session_state.semantic_shadow_results[-4:],invoke)
        st.session_state.semantic_shadow_results.append(result)
if st.session_state.semantic_shadow_results:
    latest=st.session_state.semantic_shadow_results[-1];c1,c2,c3,c4=st.columns(4);c1.metric("Ruta",latest["decision"]["route"]);c2.metric("Intención",latest["decision"]["intent"]);c3.metric("LLM",latest["llm_calls"]);c4.metric("Retrieval",latest["retrieval_calls"]);st.json(latest)
    st.download_button("Descargar resultados",json.dumps(st.session_state.semantic_shadow_results,ensure_ascii=False,indent=2),file_name="semantic_orchestrator_shadow.json",mime="application/json",use_container_width=True)
