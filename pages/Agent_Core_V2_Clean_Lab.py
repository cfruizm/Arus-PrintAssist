import json
import streamlit as st
from app.agent_core_v2_clean.lab_session import get_store,reset_store,process_message,export_session
st.set_page_config(page_title="Agent Core V2 Clean Lab",page_icon="🧠",layout="wide")
st.title("Agent Core V2 Clean Lab")
st.caption("Fase 1 aislada: conversación y diagnóstico. Retrieval sigue deshabilitado.")
try:enabled=bool(st.secrets.get("AGENT_CORE_V2_CLEAN_LAB_ENABLED",False))
except Exception:enabled=False
if not enabled:st.info("Agrega AGENT_CORE_V2_CLEAN_LAB_ENABLED = true en Secrets.");st.stop()
store=get_store(st.session_state);t=store["telemetry"]
with st.sidebar:
 st.subheader("Control de consumo")
 c1,c2=st.columns(2);c1.metric("Tokens",f"{t['total_tokens']:,}");c2.metric("Llamadas",t["calls"])
 c3,c4=st.columns(2);c3.metric("Prompt",f"{t['prompt_tokens']:,}");c4.metric("Respuesta",f"{t['completion_tokens']:,}")
 st.metric("Errores proveedor",t["failed_calls"])
 if t["last_rate_limit"]:st.error("Se detectó límite del proveedor. Revisa el detalle de diagnóstico.")
 if t["by_purpose"]:
  st.caption("Consumo por propósito")
  for name,data in t["by_purpose"].items():st.progress(min(1.0,data["total_tokens"]/10000),text=f"{name}: {data['total_tokens']:,} tokens | {data['calls']} llamadas")
 if st.button("Nueva conversación",use_container_width=True,type="primary"):reset_store(st.session_state);st.rerun()
 st.download_button("Descargar JSON completo",json.dumps(export_session(st.session_state),ensure_ascii=False,indent=2),"agent_core_v2_clean_lab_session.json","application/json",use_container_width=True)
with st.expander("Diagnóstico actual",expanded=False):
 st.json({"memory":store["memory"].to_dict(),"telemetry":t,"errors":store["errors"]})
for i,m in enumerate(store["messages"]):
 with st.chat_message(m["role"]):st.markdown(m["content"])
for i,turn in enumerate(store["turns"],1):
 with st.expander(f"Turno {i}: diagnóstico y tokens",expanded=False):st.json({"input":turn.get("input"),"understanding":turn.get("understanding"),"decision":turn.get("decision"),"turn_metrics":turn.get("turn_metrics"),"provider_trace":turn.get("provider_trace"),"answer":turn.get("answer")})
if prompt:=st.chat_input("Escribe un mensaje"):
 with st.chat_message("user"):st.markdown(prompt)
 with st.chat_message("assistant"):
  with st.spinner("Procesando..."):result=process_message(prompt,st.secrets,st.session_state)
  st.markdown(result.get("answer",{}).get("text") or "No hubo respuesta visible.")
 st.rerun()
