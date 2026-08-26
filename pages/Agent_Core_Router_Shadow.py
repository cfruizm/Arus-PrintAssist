from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
import streamlit as st
st.set_page_config(page_title="Agent Core Router Shadow",page_icon="🧭",layout="wide")
st.title("Agent Core v1 - Router en sombra")
st.caption("Evalúa decisiones conversacionales. No cambia el chat, no llama al LLM y no consulta Chroma.")
try:debug=bool(st.secrets.get("DEBUG_UI",False));enabled=bool(st.secrets.get("AGENT_CORE_V1_ROUTER_SHADOW_ENABLED",False))
except Exception:debug=False;enabled=False
if not debug:st.warning("Requiere DEBUG_UI=true.");st.stop()
if not enabled:st.info("Agrega AGENT_CORE_V1_ROUTER_SHADOW_ENABLED=true en Secrets para habilitar esta página.");st.stop()
from app.agent_core.router_models import RouterShadowState
from app.agent_core.router_v1 import route_message
if "router_shadow_state" not in st.session_state:st.session_state.router_shadow_state=RouterShadowState()
if "router_shadow_history" not in st.session_state:st.session_state.router_shadow_history=[]
col1,col2=st.columns([3,1])
with col1:message=st.text_input("Mensaje a evaluar",value="hola")
with col2:
    if st.button("Reiniciar estado",use_container_width=True):st.session_state.router_shadow_state=RouterShadowState();st.session_state.router_shadow_history=[];st.rerun()
if st.button("Evaluar turno",type="primary",use_container_width=True):
    decision=route_message(message,st.session_state.router_shadow_state);record={"input":message,"decision":asdict(decision),"state":asdict(st.session_state.router_shadow_state),"llm_calls":0,"retrieval_calls":0,"production_response_changed":False};st.session_state.router_shadow_history.append(record)
if st.session_state.router_shadow_history:
    latest=st.session_state.router_shadow_history[-1];c1,c2,c3,c4=st.columns(4);c1.metric("Ruta",latest["decision"]["route"]);c2.metric("Confianza",latest["decision"]["confidence"]);c3.metric("LLM",0);c4.metric("Retrieval",0);st.json(latest)
case_path=Path("tools/agent_core_v1/router_shadow_cases.json")
st.divider();st.subheader("Regresión aprobada")
if st.button("Ejecutar regresión",use_container_width=True):
    cases=json.loads(case_path.read_text(encoding="utf-8"));results=[]
    for case in cases:
        state=RouterShadowState()
        if case.get("seed_topic"):state.topic.products=list(case["seed_topic"])
        if case.get("seed_case"):state.technical_case.status=case["seed_case"]
        if case.get("sequence"):
            routes=[route_message(item,state).route for item in case["sequence"]];passed=routes==case["expected_routes"];actual=routes
        else:
            decision=route_message(case["message"],state);passed=decision.route==case["expected"] and (not case.get("expected_resolution") or decision.metadata.get("resolution_status")==case["expected_resolution"]);actual=decision.route
        results.append({"id":case["id"],"passed":passed,"actual":actual})
    summary={"total":len(results),"passed":sum(r["passed"] for r in results),"failed":sum(not r["passed"] for r in results),"llm_calls":0,"retrieval_calls":0,"results":results};st.session_state.router_regression=summary
if "router_regression" in st.session_state:
    summary=st.session_state.router_regression;st.metric("Regresión",f"{summary['passed']}/{summary['total']}");st.json(summary);st.download_button("Descargar regresión JSON",json.dumps(summary,ensure_ascii=False,indent=2),file_name="stage5a_router_regression.json",mime="application/json",use_container_width=True)
