from __future__ import annotations
import json
from pathlib import Path
import streamlit as st
st.set_page_config(page_title="Agent Core Lab", page_icon="🧠", layout="wide")
st.title("Agent Core Lab")
st.caption("Evaluación multidimensional y política de evidencia híbrida.")
try:
    enabled=bool(st.secrets.get("AGENT_CORE_LAB_ENABLED",False));batch=int(st.secrets.get("AGENT_CORE_LAB_BATCH_SIZE",3));tokens=int(st.secrets.get("LLM_ORCHESTRATOR_MAX_TOKENS",220));policy=str(st.secrets.get("LLM_INTERNAL_KNOWLEDGE_POLICY","hybrid_guarded"))
except Exception:
    enabled=False;batch=3;tokens=220;policy="hybrid_guarded"
if not enabled:
    st.info("Agrega AGENT_CORE_LAB_ENABLED=true en Secrets.");st.stop()
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from app.agent_core.semantic_gateway_evaluator import evaluate_case,summarize
from app.agent_core.response_evidence_policy import evaluate_document_support,build_response_contract
sem_tab,evidence_tab=st.tabs(["Orquestador semántico","Política de evidencia"])
with sem_tab:
    cases=json.loads(Path("tools/agent_core_lab/benchmark_cases.json").read_text(encoding="utf-8"));config=load_gateway_config(st.secrets);batch=max(1,min(5,batch));tokens=max(160,min(256,tokens))
    if "agent_core_lab_records_v2" not in st.session_state:st.session_state.agent_core_lab_records_v2=[]
    st.json({"provider":config["provider"],"model":config["providers"][config["provider"]]["orchestrator_model"],"cases":len(cases),"batch_size":batch,"max_output_tokens":tokens})
    selected=st.multiselect("Casos semánticos",[c["id"] for c in cases],max_selections=batch)
    if st.button("Ejecutar casos semánticos",type="primary",disabled=not selected):
        gateway=LLMGateway(config,st.session_state)
        for case in [c for c in cases if c["id"] in selected]:st.session_state.agent_core_lab_records_v2.append(evaluate_case(gateway,case,tokens))
    if st.session_state.agent_core_lab_records_v2:
        summary=summarize(st.session_state.agent_core_lab_records_v2)
        c1,c2,c3,c4=st.columns(4);c1.metric("Casos",summary["total"]);c2.metric("Aprobación total",f"{summary['passed']}/{summary['total']}");c3.metric("Decisión operativa",f"{summary['operational_passed']}/{summary['total']}");c4.metric("Extracción de estado",f"{summary['state_extraction_passed']}/{summary['total']}")
        st.subheader("Resultados por dimensión");st.json(summary["dimensions"])
        st.json({"summary":summary,"records":st.session_state.agent_core_lab_records_v2})
        st.download_button("Descargar evaluación",json.dumps({"summary":summary,"records":st.session_state.agent_core_lab_records_v2},ensure_ascii=False,indent=2),file_name="agent_core_multidimensional_results.json",mime="application/json")
    if st.button("Limpiar resultados semánticos",use_container_width=True):st.session_state.agent_core_lab_records_v2=[];st.rerun()
with evidence_tab:
    st.write("Política activa:",policy)
    evidence_cases=json.loads(Path("tools/agent_core_lab/evidence_policy_cases.json").read_text(encoding="utf-8"))
    selected_case=st.selectbox("Escenario documental",[c["id"] for c in evidence_cases]);case=next(c for c in evidence_cases if c["id"]==selected_case)
    decision=evaluate_document_support(case["metrics"],policy,case["intent"]);contract=build_response_contract(decision)
    st.json({"input":case,"decision":decision.to_dict(),"response_contract":contract,"passed":decision.response_mode==case["expected"]})
