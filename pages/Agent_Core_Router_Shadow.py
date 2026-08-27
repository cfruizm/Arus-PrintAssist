from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
import streamlit as st
st.set_page_config(page_title="Agent Core Router Shadow",page_icon="🧭",layout="wide")
st.title("Agent Core v1 - Router en sombra")
st.caption("Corrección 5A: puntuación conversacional, cortesía y continuidad verificable.")
try:debug=bool(st.secrets.get("DEBUG_UI",False));enabled=bool(st.secrets.get("AGENT_CORE_V1_ROUTER_SHADOW_ENABLED",False))
except Exception:debug=False;enabled=False
if not debug:st.warning("Requiere DEBUG_UI=true.");st.stop()
if not enabled:st.info("Agrega AGENT_CORE_V1_ROUTER_SHADOW_ENABLED=true en Secrets.");st.stop()
from app.agent_core.router_models import RouterShadowState
from app.agent_core.router_v1 import route_message
if "router_shadow_state_v2" not in st.session_state:st.session_state.router_shadow_state_v2=RouterShadowState()
if "router_shadow_history_v2" not in st.session_state:st.session_state.router_shadow_history_v2=[]
col1,col2=st.columns([3,1])
with col1:message=st.text_input("Mensaje a evaluar",value="Tengo problemas.")
with col2:
    if st.button("Reiniciar secuencia",use_container_width=True):st.session_state.router_shadow_state_v2=RouterShadowState();st.session_state.router_shadow_history_v2=[];st.rerun()
if st.button("Evaluar turno",type="primary",use_container_width=True):
    decision=route_message(message,st.session_state.router_shadow_state_v2);record={"input":message,"decision":asdict(decision),"state":asdict(st.session_state.router_shadow_state_v2),"llm_calls":0,"retrieval_calls":0,"production_response_changed":False};st.session_state.router_shadow_history_v2.append(record)
if st.session_state.router_shadow_history_v2:
    latest=st.session_state.router_shadow_history_v2[-1];c1,c2,c3,c4=st.columns(4);c1.metric("Ruta",latest["decision"]["route"]);c2.metric("Turno",latest["state"]["turn_number"]);c3.metric("LLM",0);c4.metric("Retrieval",0);st.json(latest)
    with st.expander("Historial completo de la secuencia",expanded=False):st.json(st.session_state.router_shadow_history_v2)
st.divider();st.subheader("Regresión ampliada")
case_path=Path("tools/agent_core_v1/router_shadow_cases.json")
if st.button("Ejecutar regresión ampliada",use_container_width=True):
    cases=json.loads(case_path.read_text(encoding="utf-8"));results=[]
    for case in cases:
        state=RouterShadowState()
        if case.get("seed_topic"):state.topic.products=list(case["seed_topic"])
        if case.get("seed_case"):state.technical_case.status=case["seed_case"]
        if case.get("sequence"):
            routes=[route_message(item,state).route for item in case["sequence"]];passed=routes==case["expected_routes"]
            final=case.get("final") or {}
            if final:
                passed=passed and state.turn_number==final["turn_number"] and final["product"] in state.topic.products and state.technical_case.status==final["status"] and state.technical_case.resolution_status==final["resolution_status"] and state.technical_case.affected_users==final["affected_users"]
            actual={"routes":routes,"turn_number":state.turn_number,"products":state.topic.products,"status":state.technical_case.status,"resolution_status":state.technical_case.resolution_status,"affected_users":state.technical_case.affected_users}
        else:
            decision=route_message(case["message"],state);passed=decision.route==case["expected"] and (not case.get("resolution") or decision.metadata.get("resolution_status")==case["resolution"])
            if case.get("url_suffix"):passed=passed and decision.metadata.get("urls",[""])[0].endswith(case["url_suffix"])
            actual=decision.route
        results.append({"id":case["id"],"passed":passed,"actual":actual})
    summary={"total":len(results),"passed":sum(r["passed"] for r in results),"failed":sum(not r["passed"] for r in results),"llm_calls":0,"retrieval_calls":0,"results":results};st.session_state.router_regression_v2=summary
if "router_regression_v2" in st.session_state:
    summary=st.session_state.router_regression_v2;st.metric("Regresión",f"{summary['passed']}/{summary['total']}");st.json(summary);st.download_button("Descargar regresión JSON",json.dumps(summary,ensure_ascii=False,indent=2),file_name="stage5a_router_regression_corrected.json",mime="application/json",use_container_width=True)
