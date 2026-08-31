from __future__ import annotations
import json
from pathlib import Path
import streamlit as st
st.set_page_config(page_title="Agent Core Lab",page_icon="🧠",layout="wide")
st.title("Agent Core Lab")
st.caption("Orquestación semántica, evidencia, respuesta híbrida y sombra real.")
try:enabled=bool(st.secrets.get("AGENT_CORE_LAB_ENABLED",False));batch=int(st.secrets.get("AGENT_CORE_LAB_BATCH_SIZE",3));tokens=int(st.secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",180));policy=str(st.secrets.get("LLM_INTERNAL_KNOWLEDGE_POLICY","hybrid_guarded"));answer_tokens=int(st.secrets.get("LLM_ANSWER_MAX_TOKENS",400))
except Exception:enabled=False;batch=3;tokens=180;policy="hybrid_guarded";answer_tokens=400
if not enabled:st.info("Agrega AGENT_CORE_LAB_ENABLED=true en Secrets.");st.stop()
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from app.agent_core.semantic_gateway_evaluator import evaluate_case,summarize
from app.agent_core.response_evidence_policy import evaluate_document_support,build_response_contract
from app.integration.semantic_real_chat_shadow import summarize_records
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.agent_core.hybrid_response_lab import run_hybrid_response_lab
sem_tab,evidence_tab,answer_tab,real_tab=st.tabs(["Orquestador semántico","Política de evidencia","Respuesta híbrida","Chat real en sombra"])
with sem_tab:
 cases=json.loads(Path("tools/agent_core_lab/benchmark_cases.json").read_text(encoding="utf-8"));config=load_gateway_config(st.secrets)
 if "agent_core_act_records" not in st.session_state:st.session_state.agent_core_act_records=[]
 st.json({"contract":"conversation_act_v1","provider":config["provider"],"model":config["providers"][config["provider"]]["orchestrator_model"],"cases":len(cases)})
 selected=st.multiselect("Casos semánticos",[c["id"] for c in cases],max_selections=max(1,min(5,batch)))
 if st.button("Ejecutar casos semánticos",disabled=not selected):
  gateway=LLMGateway(config,st.session_state)
  for case in [c for c in cases if c["id"] in selected]:st.session_state.agent_core_act_records.append(evaluate_case(gateway,case,max(120,min(220,tokens))))
 if st.session_state.agent_core_act_records:st.json({"summary":summarize(st.session_state.agent_core_act_records),"records":st.session_state.agent_core_act_records})
with evidence_tab:
 st.write("Política activa:",policy);items=json.loads(Path("tools/agent_core_lab/evidence_policy_cases.json").read_text(encoding="utf-8"));sid=st.selectbox("Escenario documental",[x["id"] for x in items]);item=next(x for x in items if x["id"]==sid);decision=evaluate_document_support(item["metrics"],policy,item["intent"]);st.json({"input":item,"decision":decision.to_dict(),"response_contract":build_response_contract(decision),"expected":item["expected"]})
with answer_tab:
 st.warning("Laboratorio aislado. Retrieval real; la política puede omitir el LLM cuando la cobertura sea insuficiente.")
 query=st.text_area("Consulta técnica",value="Los trabajos dejan de verse después del envío en PaperCut MF. ¿Qué validación sigue?",height=90);product=st.text_input("Producto conocido",value="PaperCut MF");symptom=st.text_input("Síntoma confirmado",value="Los trabajos dejan de verse después del envío");failed=st.text_input("Acción fallida",value="Reinicio del proveedor de impresión")
 if st.button("1. Recuperar evidencia",type="primary"):st.session_state.hybrid_retrieval=retrieve_from_existing_backend(query,6)
 if "hybrid_retrieval" in st.session_state:st.json(st.session_state.hybrid_retrieval)
 if st.button("2. Evaluar y generar respuesta",disabled=not bool(st.session_state.get("hybrid_retrieval",{}).get("ok"))):
  state={"products":[product] if product else [],"symptoms":[symptom] if symptom else [],"failed_actions":[failed] if failed else []};gateway=LLMGateway(load_gateway_config(st.secrets),st.session_state);st.session_state.hybrid_answer=run_hybrid_response_lab(gateway,st.session_state.hybrid_retrieval,query,state,"troubleshooting",policy,answer_tokens)
 if "hybrid_answer" in st.session_state:
  result=st.session_state.hybrid_answer;st.json(result);st.markdown(result.get("answer_result",{}).get("text","") or "");st.download_button("Descargar respuesta",json.dumps(result,ensure_ascii=False,indent=2),file_name="agent_core_hybrid_response_guarded.json",mime="application/json")
with real_tab:
 records=list(st.session_state.get("agent_core_semantic_real_chat_records",[]) or []);st.json({"summary":summarize_records(records),"records":records})
