from __future__ import annotations
import json
import streamlit as st
st.set_page_config(page_title="LLM Provider Diagnostics",page_icon="🔌",layout="wide")
st.title("LLM Provider Gateway P1")
st.caption("Prueba multiproveedor aislada. No modifica el chat, no consulta Chroma y hace una llamada por clic.")
try:debug=bool(st.secrets.get("DEBUG_UI",False))
except Exception:debug=False
if not debug:st.warning("Requiere DEBUG_UI=true.");st.stop()
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from app.llm_gateway.models import LLMRequest
config=load_gateway_config(st.secrets)
st.json({"provider":config["provider"],"fallback_enabled":config["fallback_enabled"],"fallback_provider":config["fallback_provider"],"calls_used":st.session_state.get("llm_gateway_calls",0),"tokens_used":st.session_state.get("llm_gateway_tokens",0)})
purpose=st.selectbox("Propósito",["semantic_orchestrator","technical_answer"])
max_tokens=st.slider("Máximo de salida",32,512,120 if purpose=="semantic_orchestrator" else 256,8)
prompt=st.text_area("Mensaje de prueba",value='Devuelve únicamente JSON compacto: {"ok":true,"provider_test":"passed"}',height=90)
if st.button("Ejecutar una llamada",type="primary",use_container_width=True):
    gateway=LLMGateway(config,st.session_state);request=LLMRequest([{"role":"user","content":prompt}],purpose,max_tokens,0.0)
    result=gateway.complete(request);st.session_state["llm_gateway_last_result"]=result.to_dict()
if "llm_gateway_last_result" in st.session_state:
    result=st.session_state["llm_gateway_last_result"]
    if result["ok"]:st.success("Proveedor respondió correctamente.")
    else:st.error(result["error_message"] or result["error_code"])
    st.json(result)
    st.download_button("Descargar diagnóstico",json.dumps(result,ensure_ascii=False,indent=2),file_name="llm_provider_diagnostic.json",mime="application/json",use_container_width=True)
if st.button("Reiniciar presupuesto local",use_container_width=True):
    for key in ["llm_gateway_calls","llm_gateway_tokens","llm_gateway_history","llm_gateway_last_result"]:st.session_state.pop(key,None)
    st.rerun()
