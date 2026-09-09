import json
import streamlit as st
from app.agent_core_v2_clean.lab_session import get_store,reset_store,process_message,export_session
st.set_page_config(page_title="Agent Core V2 Clean Lab",page_icon="🧠",layout="wide")
st.title("Agent Core V2 Clean Lab")
st.caption("Laboratorio presupuestado. Retrieval deshabilitado.")
try:enabled=bool(st.secrets.get("AGENT_CORE_V2_CLEAN_LAB_ENABLED",False))
except Exception:enabled=False
if not enabled:st.info("Agrega AGENT_CORE_V2_CLEAN_LAB_ENABLED = true en Secrets.");st.stop()
store=get_store(st.session_state);t=store["telemetry"];b=store["budget"]
with st.sidebar:
 st.subheader("Presupuesto")
 mode=st.selectbox("Modo",["live_economy","dry_run"],index=0 if b["mode"]=="live_economy" else 1);b["mode"]=mode
 b["max_session_tokens"]=st.number_input("Tope sesión",1000,20000,int(b["max_session_tokens"]),500)
 b["max_session_calls"]=st.number_input("Tope llamadas",1,50,int(b["max_session_calls"]),1)
 remaining=max(0,b["max_session_tokens"]-t["total_tokens"]);st.metric("Tokens usados",f"{t['total_tokens']:,}");st.metric("Disponibles sesión",f"{remaining:,}");st.progress(min(1.0,t["total_tokens"]/max(1,b["max_session_tokens"])))
 c1,c2=st.columns(2);c1.metric("Llamadas",t["calls"]);c2.metric("Errores",t["failed_calls"])
 st.caption(f"Prompt {t['prompt_tokens']:,} | Salida {t['completion_tokens']:,}")
 if t["last_rate_limit"]:st.error("Proveedor limitado. Las nuevas llamadas quedan bloqueadas en esta sesión.")
 if st.button("Nueva conversación",use_container_width=True,type="primary"):reset_store(st.session_state);st.rerun()
 st.download_button("Descargar JSON",json.dumps(export_session(st.session_state),ensure_ascii=False,indent=2),"agent_core_v2_clean_lab_session.json","application/json",use_container_width=True)
with st.expander("Diagnóstico",False):st.json({"memory":store["memory"].to_dict(),"budget":b,"telemetry":t,"errors":store["errors"]})
for m in store["messages"]:
 with st.chat_message(m["role"]):st.markdown(m["content"])
for i,turn in enumerate(store["turns"],1):
 with st.expander(f"Turno {i} | {turn.get('turn_metrics',{}).get('total_tokens',0)} tokens",False):st.json(turn)
if prompt:=st.chat_input("Escribe un mensaje"):
 with st.chat_message("user"):st.markdown(prompt)
 with st.chat_message("assistant"):
  with st.spinner("Procesando..."):r=process_message(prompt,st.secrets,st.session_state)
  st.markdown(r.get("answer",{}).get("text") or "Sin respuesta")
 st.rerun()
