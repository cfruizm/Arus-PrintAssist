import json
from pathlib import Path
import streamlit as st
from app.agent_core_v2.multiturn_lab import run_multiturn_scenario
st.set_page_config(page_title="Agent Core v2 Multiturn Lab",layout="wide")
st.title("Agent Core v2, Fase 3: benchmark multitur")
st.caption("Cada escenario conserva un único estado entre turnos. No modifica el chat productivo. La latencia no se evalúa.")
scenarios=json.loads(Path("tools/agent_core_v2/multiturn_scenarios.json").read_text(encoding="utf-8"));options={f"{x['name']} ({x['id']})":x for x in scenarios};selected=options[st.selectbox("Escenario",list(options))]
for i,message in enumerate(selected["messages"],1):st.markdown(f"**Turno {i}:** {message}")
st.warning("Ejecuta un escenario por vez. Un escenario de tres turnos puede consumir varias llamadas según la ruta documental elegida.")
if st.button("Ejecutar conversación multitur",type="primary"):
 with st.spinner("Ejecutando conversación con estado compartido..."):st.session_state["agent_core_v2_multiturn_result"]=run_multiturn_scenario(selected,st.secrets,st.session_state)
r=st.session_state.get("agent_core_v2_multiturn_result")
if r:
 color="success" if r.get("checkpoint_passed") else "warning";getattr(st,color)(f"Checkpoint de conversación: {r.get('conversation_checkpoint',{}).get('status','unknown').upper()}")
 a,b,c,d=st.columns(4);a.metric("Turnos",len(r.get("turns") or []));b.metric("Llamadas",r.get("usage",{}).get("calls",0));c.metric("Tokens",r.get("usage",{}).get("total_tokens",0));d.metric("Llamadas evitadas",r.get("adaptive_savings",{}).get("calls_avoided",0))
 st.caption(f"Latencia observada: {r.get('latency_ms',0)/1000:.2f} s. No evaluada.")
 for i,turn in enumerate(r.get("turns") or [],1):
  with st.expander(f"Turno {i}: decisión, memoria y respuesta",expanded=True):
   st.markdown("**Entrada**");st.write(turn.get("input"));st.markdown("**Decisión**");st.json(turn.get("decision"));st.markdown("**Estado después**");st.json(turn.get("state_after"));st.markdown("**Respuesta**");st.markdown((turn.get("answer") or {}).get("text") or "Sin respuesta visible");st.markdown("**Checkpoint del turno**");st.json(turn.get("multiturn_checkpoint"));st.markdown("**Ruta y costo**");st.json(turn.get("cost_route_metrics") or {})
 st.markdown("**Checkpoint de conversación**");st.json(r.get("conversation_checkpoint"));st.markdown("**Estado final**");st.json(r.get("final_state"));st.download_button("Descargar resultado JSON",json.dumps(r,ensure_ascii=False,indent=2),file_name=f"agent_core_v2_multiturn_{r.get('scenario_id')}.json",mime="application/json")
