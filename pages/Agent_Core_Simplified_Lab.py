import json
from pathlib import Path
import streamlit as st
from app.agent_core_simplified import SimplifiedAgentRuntime,ConversationState
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
st.set_page_config(page_title="Agent Core Simplified Lab",layout="wide");st.title("Agent Core Simplified Runtime");st.caption("Máximo normal: una llamada de planificación y una de respuesta. Sin juez, reparación ni expansión LLM.")
scenarios=json.loads(Path("tools/agent_core_simplified/benchmark_scenarios.json").read_text(encoding="utf-8"));opts={x["id"]:x for x in scenarios};selected=opts[st.selectbox("Escenario",list(opts))]
for i,m in enumerate(selected["messages"],1):st.write(f"{i}. {m}")
if st.button("Ejecutar conversación",type="primary"):
 gateway=LLMGateway(load_gateway_config(st.secrets),st.session_state)
 def ret(q,n):
  r=retrieve_from_existing_backend(q,n);return list(r.get("evidence") or []) if isinstance(r,dict) and r.get("ok") else []
 runtime=SimplifiedAgentRuntime(gateway,ret);state=ConversationState(conversation_id=selected["id"]);turns=[]
 for m in selected["messages"]:turns.append(runtime.process(m,state))
 st.session_state["simplified_result"]={"scenario_id":selected["id"],"turns":turns,"final_state":state.to_dict(),"production_changed":False}
r=st.session_state.get("simplified_result")
if r:
 st.success("Ejecución completada")
 for i,t in enumerate(r["turns"],1):
  with st.expander(f"Turno {i}",expanded=True):st.json(t["plan"]);st.write(t["answer"].get("answer"));st.json(t["metrics"])
 st.download_button("Descargar JSON",json.dumps(r,ensure_ascii=False,indent=2),file_name=f"simplified_{r['scenario_id']}.json")
