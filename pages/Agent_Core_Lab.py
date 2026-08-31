from __future__ import annotations
import json
from pathlib import Path
import streamlit as st
st.set_page_config(page_title="Agent Core Lab",page_icon="🧠",layout="wide")
st.title("Agent Core Lab")
st.caption("Laboratorio semántico, política de evidencia y observación del chat real.")
try:
 enabled=bool(st.secrets.get("AGENT_CORE_LAB_ENABLED",False));batch=int(st.secrets.get("AGENT_CORE_LAB_BATCH_SIZE",3));tokens=int(st.secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",180));policy=str(st.secrets.get("LLM_INTERNAL_KNOWLEDGE_POLICY","hybrid_guarded"));real_shadow=bool(st.secrets.get("AGENT_CORE_SEMANTIC_REAL_CHAT_SHADOW_ENABLED",False))
except Exception:enabled=False;batch=3;tokens=180;policy="hybrid_guarded";real_shadow=False
if not enabled:st.info("Agrega AGENT_CORE_LAB_ENABLED=true en Secrets.");st.stop()
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from app.agent_core.semantic_gateway_evaluator import evaluate_case,summarize
from app.agent_core.response_evidence_policy import evaluate_document_support,build_response_contract
from app.integration.semantic_real_chat_shadow import summarize_records
sem_tab,evidence_tab,real_tab=st.tabs(["Orquestador semántico","Política de evidencia","Chat real en sombra"])
with sem_tab:
 cases=json.loads(Path("tools/agent_core_lab/benchmark_cases.json").read_text(encoding="utf-8"));config=load_gateway_config(st.secrets);batch=max(1,min(5,batch));tokens=max(120,min(220,tokens))
 if "agent_core_act_records" not in st.session_state:st.session_state.agent_core_act_records=[]
 st.json({"contract":"conversation_act_v1","provider":config["provider"],"model":config["providers"][config["provider"]]["orchestrator_model"],"cases":len(cases),"batch_size":batch,"max_output_tokens":tokens})
 selected=st.multiselect("Casos semánticos",[c["id"] for c in cases],max_selections=batch)
 if st.button("Ejecutar casos semánticos",type="primary",disabled=not selected):
  gateway=LLMGateway(config,st.session_state)
  for case in [c for c in cases if c["id"] in selected]:st.session_state.agent_core_act_records.append(evaluate_case(gateway,case,tokens))
 if st.session_state.agent_core_act_records:
  summary=summarize(st.session_state.agent_core_act_records);st.json({"summary":summary,"records":st.session_state.agent_core_act_records});st.download_button("Descargar evaluación",json.dumps({"summary":summary,"records":st.session_state.agent_core_act_records},ensure_ascii=False,indent=2),file_name="agent_core_conversation_act_results.json",mime="application/json")
 if st.button("Limpiar resultados semánticos"):st.session_state.agent_core_act_records=[];st.rerun()
with evidence_tab:
 st.write("Política activa:",policy);evidence_cases=json.loads(Path("tools/agent_core_lab/evidence_policy_cases.json").read_text(encoding="utf-8"));selected_case=st.selectbox("Escenario documental",[c["id"] for c in evidence_cases]);case=next(c for c in evidence_cases if c["id"]==selected_case);decision=evaluate_document_support(case["metrics"],policy,case["intent"]);st.json({"input":case,"decision":decision.to_dict(),"response_contract":build_response_contract(decision),"passed":decision.response_mode==case["expected"]})
with real_tab:
 st.write("**Flag activo:**",real_shadow);records=list(st.session_state.get("agent_core_semantic_real_chat_records",[]) or []);summary=summarize_records(records)
 c1,c2,c3,c4=st.columns(4);c1.metric("Turnos",summary["total"]);c2.metric("Correctos",summary["ok"]);c3.metric("Tokens",summary["total_tokens"]);c4.metric("Normalizados",summary["normalizations"])
 st.json(summary)
 if records:
  st.subheader("Último turno");st.json(records[-1])
  with st.expander("Historial completo"):st.json(records)
  st.download_button("Descargar sombra real",json.dumps({"summary":summary,"records":records},ensure_ascii=False,indent=2),file_name="agent_core_semantic_real_chat_shadow.json",mime="application/json")
 else:st.info("No hay registros. Activa el flag y usa el chat principal.")
 if st.button("Limpiar sombra real"):st.session_state["agent_core_semantic_real_chat_records"]=[];st.session_state.pop("agent_core_semantic_real_chat_last_record",None);st.rerun()
