import json
import streamlit as st
from app.agent_core_v2_clean.lab_session import get_store,reset_store,process_message,export_session
from app.agent_core_v2_clean.budget import BudgetPolicy
from app.agent_core_v2_clean.scenario_runner import run_all
st.set_page_config(page_title="Agent Core V2 Clean Lab",page_icon="🧠",layout="wide")
st.title("Agent Core V2 Clean Lab")
try:enabled=bool(st.secrets.get("AGENT_CORE_V2_CLEAN_LAB_ENABLED",False))
except Exception:enabled=False
if not enabled:st.info("Agrega AGENT_CORE_V2_CLEAN_LAB_ENABLED = true en Secrets.");st.stop()
store=get_store(st.session_state);t=store["telemetry"]
with st.sidebar:
 st.subheader("Modo de laboratorio")
 mode=st.radio("Modo",["normal","economy","deterministic"],horizontal=False,index=["normal","economy","deterministic"].index(store.get("budget",{}).get("mode","normal")))
 preset=BudgetPolicy.for_mode(mode);store["budget"]=preset.to_dict()
 if mode!="deterministic":
  st.metric("Tokens usados",f"{t['total_tokens']:,}");st.metric("Disponibles",f"{max(0,preset.max_session_tokens-t['total_tokens']):,}");st.progress(min(1.0,t['total_tokens']/max(1,preset.max_session_tokens)));st.caption(f"Llamadas {t['calls']}/{preset.max_session_calls} | Errores {t['failed_calls']}")
 else:st.success("Cero llamadas LLM y cero tokens")
 if st.button("Nueva conversación",use_container_width=True,type="primary"):reset_store(st.session_state);st.rerun()
 st.download_button("Descargar JSON",json.dumps(export_session(st.session_state),ensure_ascii=False,indent=2),"agent_core_v2_clean_lab_session.json","application/json",use_container_width=True)
if mode=="deterministic":
 st.subheader("Diagnóstico determinista")
 st.caption("Ejecuta memoria, política, cambios de tema, casos y fallos de proveedor con fixtures estructurados. No interpreta mensajes libres.")
 if st.button("Ejecutar todos los escenarios",type="primary"):
  results=run_all();st.session_state["v2_clean_scenario_results"]=results
 results=st.session_state.get("v2_clean_scenario_results",[])
 if results:
  a,b,c=st.columns(3);a.metric("Escenarios",len(results));b.metric("Aprobados",sum(x["passed"] for x in results));c.metric("Tokens",0)
  for r in results:
   with st.expander(("✅ " if r["passed"] else "❌ ")+r["name"],expanded=not r["passed"]):st.json(r)
 st.info("Para lenguaje libre cambia a normal o economy.")
else:
 st.caption("Normal prioriza calidad. Economy reduce tokens. Retrieval continúa deshabilitado en esta fase.")
 for m in store["messages"]:
  with st.chat_message(m["role"]):st.markdown(m["content"])
 if prompt:=st.chat_input("Escribe un mensaje"):
  with st.chat_message("user"):st.markdown(prompt)
  with st.chat_message("assistant"):
   with st.spinner("Procesando..."):r=process_message(prompt,st.secrets,st.session_state)
   st.markdown(r.get("answer",{}).get("text") or "Sin respuesta")
  st.rerun()
with st.expander("Diagnóstico técnico",False):st.json({"memory":store["memory"].to_dict(),"budget":store["budget"],"telemetry":t,"errors":store["errors"]})
