from __future__ import annotations
import json
import streamlit as st
st.set_page_config(page_title="LLM Provider Diagnostics",page_icon="🔌",layout="wide")
st.title("LLM Provider Gateway P1 - Diagnóstico seguro")
st.caption("Primero valida la clave y consulta /models sin consumir tokens de inferencia. El chat completion queda separado.")
try:debug=bool(st.secrets.get("DEBUG_UI",False))
except Exception:debug=False
if not debug:st.warning("Requiere DEBUG_UI=true.");st.stop()
from app.llm_gateway.config import load_gateway_config,model_for
from app.llm_gateway.gateway import LLMGateway
from app.llm_gateway.models import LLMRequest
from app.llm_gateway.providers.groq_provider import diagnose_groq
config=load_gateway_config(st.secrets);groq_cfg=config["providers"]["groq"];configured_model=groq_cfg["orchestrator_model"]
st.json({"provider":config["provider"],"configured_model":configured_model,"fallback_enabled":config["fallback_enabled"],"calls_used":st.session_state.get("llm_gateway_calls",0),"tokens_used":st.session_state.get("llm_gateway_tokens",0)})
if st.button("1. Diagnosticar autenticación sin inferencia",type="primary",use_container_width=True):
    st.session_state["groq_auth_diagnostic"]=diagnose_groq(groq_cfg.get("api_key"),configured_model)
if "groq_auth_diagnostic" in st.session_state:
    diagnosis=st.session_state["groq_auth_diagnostic"]
    if diagnosis.get("authenticated") and diagnosis.get("model_available"):st.success("Clave válida y modelo disponible.")
    elif diagnosis.get("authenticated"):st.warning("Clave válida, pero el modelo configurado no aparece en /models.")
    else:st.error(diagnosis.get("provider_error_message") or diagnosis.get("error_code"))
    st.json(diagnosis)
    st.download_button("Descargar diagnóstico de autenticación",json.dumps(diagnosis,ensure_ascii=False,indent=2),file_name="groq_auth_diagnostic.json",mime="application/json",use_container_width=True)
st.divider();st.subheader("2. Chat completion mínimo")
auth_ok=bool((st.session_state.get("groq_auth_diagnostic") or {}).get("authenticated") and (st.session_state.get("groq_auth_diagnostic") or {}).get("model_available"))
max_tokens=st.slider("Máximo de salida",32,128,64,8);prompt=st.text_area("Mensaje",value='Devuelve solo JSON: {"ok":true}',height=70)
if st.button("Ejecutar chat mínimo",use_container_width=True,disabled=not auth_ok):
    result=LLMGateway(config,st.session_state).complete(LLMRequest([{"role":"user","content":prompt}],"semantic_orchestrator",max_tokens,0.0));st.session_state["llm_gateway_last_result"]=result.to_dict()
if "llm_gateway_last_result" in st.session_state:st.json(st.session_state["llm_gateway_last_result"])
