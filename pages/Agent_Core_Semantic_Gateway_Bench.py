from __future__ import annotations
import json
from pathlib import Path
import streamlit as st
st.set_page_config(page_title="Semantic Gateway Bench",page_icon="🧠",layout="wide")
st.title("Banco semántico multiproveedor P2")
st.caption("Evalúa comprensión semántica mediante LLM Gateway. No cambia el chat y no ejecuta retrieval.")
try:debug=bool(st.secrets.get("DEBUG_UI",False));enabled=bool(st.secrets.get("SEMANTIC_GATEWAY_BENCH_ENABLED",False));batch_limit=int(st.secrets.get("SEMANTIC_GATEWAY_BATCH_SIZE",3));max_tokens=int(st.secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",180))
except Exception:debug=False;enabled=False;batch_limit=3;max_tokens=180
if not debug:st.warning("Requiere DEBUG_UI=true.");st.stop()
if not enabled:st.info("Agrega SEMANTIC_GATEWAY_BENCH_ENABLED=true para habilitar el banco.");st.stop()
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from app.agent_core.semantic_gateway_evaluator import evaluate_case,summarize
cases=json.loads(Path("tools/llm_gateway/semantic_benchmark_cases.json").read_text(encoding="utf-8"))
config=load_gateway_config(st.secrets);batch_limit=max(1,min(5,batch_limit));max_tokens=max(96,min(256,max_tokens))
if "semantic_gateway_records" not in st.session_state:st.session_state.semantic_gateway_records=[]
st.json({"provider":config["provider"],"orchestrator_model":config["providers"][config["provider"]]["orchestrator_model"],"batch_limit":batch_limit,"max_output_tokens":max_tokens,"session_calls":st.session_state.get("llm_gateway_calls",0),"session_tokens":st.session_state.get("llm_gateway_tokens",0)})
ids=[c["id"] for c in cases];selected=st.multiselect("Casos",ids,default=ids[:1],max_selections=batch_limit)
if st.button("Ejecutar selección",type="primary",use_container_width=True,disabled=not selected):
 gateway=LLMGateway(config,st.session_state)
 for case in [c for c in cases if c["id"] in selected]:
  with st.spinner(f"Evaluando {case['id']}..."):st.session_state.semantic_gateway_records.append(evaluate_case(gateway,case,max_tokens))
if st.session_state.semantic_gateway_records:
 summary=summarize(st.session_state.semantic_gateway_records);c1,c2,c3,c4=st.columns(4);c1.metric("Casos",summary["total"]);c2.metric("Aprobados",summary["passed"]);c3.metric("Tokens",summary["usage"]["total_tokens"]);c4.metric("Latencia media",f"{summary['average_latency_ms']} ms")
 st.json({"summary":summary,"records":st.session_state.semantic_gateway_records})
 st.download_button("Descargar resultados",json.dumps({"summary":summary,"records":st.session_state.semantic_gateway_records},ensure_ascii=False,indent=2),file_name="semantic_gateway_p2_results.json",mime="application/json",use_container_width=True)
if st.button("Limpiar resultados locales",use_container_width=True):st.session_state.semantic_gateway_records=[];st.rerun()
