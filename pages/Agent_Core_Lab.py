from __future__ import annotations
import json
from pathlib import Path
import streamlit as st
st.set_page_config(page_title="Agent Core Lab",page_icon="🧠",layout="wide")
st.title("Agent Core Lab")
st.caption("Laboratorio consolidado para evaluación semántica multiproveedor.")
try:enabled=bool(st.secrets.get("AGENT_CORE_LAB_ENABLED",False));batch=int(st.secrets.get("AGENT_CORE_LAB_BATCH_SIZE",3));tokens=int(st.secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",220))
except Exception:enabled=False;batch=3;tokens=220
if not enabled:st.info("Agrega AGENT_CORE_LAB_ENABLED=true en Secrets.");st.stop()
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from app.agent_core.semantic_gateway_evaluator import evaluate_case,summarize
cases=json.loads(Path("tools/agent_core_lab/benchmark_cases.json").read_text(encoding="utf-8"));config=load_gateway_config(st.secrets);batch=max(1,min(5,batch));tokens=max(160,min(256,tokens))
if "agent_core_lab_records" not in st.session_state:st.session_state.agent_core_lab_records=[]
st.json({"provider":config["provider"],"model":config["providers"][config["provider"]]["orchestrator_model"],"cases":len(cases),"batch_size":batch,"max_output_tokens":tokens,"calls":st.session_state.get("llm_gateway_calls",0),"tokens_used":st.session_state.get("llm_gateway_tokens",0)})
selected=st.multiselect("Casos",[c["id"] for c in cases],max_selections=batch)
if st.button("Ejecutar",type="primary",use_container_width=True,disabled=not selected):
 gateway=LLMGateway(config,st.session_state)
 for case in [c for c in cases if c["id"] in selected]:st.session_state.agent_core_lab_records.append(evaluate_case(gateway,case,tokens))
if st.session_state.agent_core_lab_records:
 summary=summarize(st.session_state.agent_core_lab_records);c1,c2,c3,c4=st.columns(4);c1.metric("Casos",summary["total"]);c2.metric("Aprobados",summary["passed"]);c3.metric("Tokens",summary["usage"]["total_tokens"]);c4.metric("Latencia media",f"{summary['average_latency_ms']} ms");st.json({"summary":summary,"records":st.session_state.agent_core_lab_records});st.download_button("Descargar",json.dumps({"summary":summary,"records":st.session_state.agent_core_lab_records},ensure_ascii=False,indent=2),file_name="agent_core_lab_results.json",mime="application/json",use_container_width=True)
if st.button("Limpiar resultados",use_container_width=True):st.session_state.agent_core_lab_records=[];st.rerun()
