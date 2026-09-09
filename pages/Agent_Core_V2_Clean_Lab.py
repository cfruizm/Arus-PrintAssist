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
 modes=["normal","economy","deterministic"];current=store.get("budget",{}).get("mode","normal");mode=st.radio("Modo",modes,index=modes.index(current) if current in modes else 0)
 preset=BudgetPolicy.for_mode(mode);store["budget"]=preset.to_dict()
 if mode!="deterministic":
  used=int(t.get("total_tokens",0));calls=int(t.get("calls",0));errors=int(t.get("functional_failed_calls",t.get("failed_calls",0)))
  st.metric("Tokens usados",f"{used:,}");st.metric("Disponibles",f"{max(0,preset.max_session_tokens-used):,}");st.progress(min(1.0,used/max(1,preset.max_session_tokens)));st.caption(f"Llamadas {calls}/{preset.max_session_calls} | Fallos funcionales {errors}")
 else:st.success("Cero llamadas LLM y cero tokens")
 if st.button("Nueva conversación",use_container_width=True,type="primary"):reset_store(st.session_state);st.rerun()
 st.download_button("Descargar JSON",json.dumps(export_session(st.session_state),ensure_ascii=False,indent=2),"agent_core_v2_clean_lab_session.json","application/json",use_container_width=True)
if mode=="deterministic":
 st.subheader("Diagnóstico determinista");st.caption("Memoria, política, estado y degradación con cero llamadas LLM.")
 if st.button("Ejecutar todos los escenarios",type="primary"):
  store["deterministic_results"]=run_all();st.rerun()
 results=store.get("deterministic_results",[])
 if results:
  a,b,c=st.columns(3);a.metric("Escenarios",len(results));b.metric("Aprobados",sum(x["passed"] for x in results));c.metric("Tokens",0)
  for r in results:
   with st.expander(("✅ " if r["passed"] else "❌ ")+r["name"],expanded=not r["passed"]):st.json(r)
 st.info("Para lenguaje libre cambia a normal o economy.")
else:
 st.caption("Normal prioriza calidad. Economy reduce tokens. Retrieval documental de solo lectura habilitado; generación documentada aún deshabilitada.")
 for m in store["messages"]:
  with st.chat_message(m["role"]):st.markdown(m["content"])

 for i,turn in enumerate(store["turns"],1):
  retrieval=turn.get("retrieval") or {}
  if retrieval.get("enabled"):
   with st.expander(f"Turno {i}: recuperación documental ({retrieval.get('count',0)} fragmentos)",expanded=False):
    st.json({"query":retrieval.get("query"),"adapter":retrieval.get("adapter"),"cache_hit":retrieval.get("cache_hit"),"document_groups":retrieval.get("document_groups"),"errors":retrieval.get("errors")})
    for source in retrieval.get("evidence") or []:
     st.markdown(f"**{source.get('id')} · {source.get('title')}** · página {source.get('page') or 'N/D'}")
     st.caption(source.get("url") or source.get("source") or "Sin ruta")
     st.write(source.get("text") or "")

 if prompt:=st.chat_input("Escribe un mensaje"):
  with st.chat_message("user"):st.markdown(prompt)
  with st.chat_message("assistant"):
   with st.spinner("Procesando..."):r=process_message(prompt,st.secrets,st.session_state)
   st.markdown(r.get("answer",{}).get("text") or "Sin respuesta")
  st.rerun()
with st.expander("Diagnóstico técnico",False):st.json({"memory":store["memory"].to_dict(),"budget":store["budget"],"telemetry":t,"errors":store["errors"]})
