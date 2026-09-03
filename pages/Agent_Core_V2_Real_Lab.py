import json
from pathlib import Path
import streamlit as st
from app.agent_core_v2.real_lab import run_real_scenario
st.set_page_config(page_title="Agent Core v2 Real Lab",layout="wide");st.title("Agent Core v2, Fase 2B: laboratorio real");st.caption("La latencia se registra, pero no se evalúa durante esta fase.")
sc=json.loads(Path("tools/agent_core_v2/real_lab_scenarios.json").read_text(encoding="utf-8"));opts={f"{x['name']} ({x['id']})":x for x in sc};sel=opts[st.selectbox("Escenario",list(opts))];st.code("\n".join(sel["messages"]),language="text");st.warning("Ejecuta un escenario una sola vez para controlar créditos.")
if st.button("Ejecutar escenario real",type="primary"):
 with st.spinner("Ejecutando interpretación, retrieval y respuesta..."):st.session_state["agent_core_v2_real_lab_last_result"]=run_real_scenario(sel,st.secrets,st.session_state)
r=st.session_state.get("agent_core_v2_real_lab_last_result")
if r:
 color={"passed":"success","partial":"warning","failed":"error"}.get(r.get("functional_result"),"info");getattr(st,color)(f"Resultado funcional: {r.get('functional_result','unknown').upper()}")
 a,b,c,d=st.columns(4);a.metric("Ejecución",r.get("status"));b.metric("Resultado funcional",r.get("functional_result"));c.metric("Llamadas",r.get("usage",{}).get("calls",0));d.metric("Tokens",r.get("usage",{}).get("total_tokens",0));st.caption(f"Latencia observada: {r.get('latency_ms',0)/1000:.2f} s. No evaluada en esta fase por posible arranque en frío.")
 if r.get("error"):st.error(r["error"])
 for i,t in enumerate(r.get("turns") or [],1):
  st.subheader(f"Turno {i}");st.markdown("**Decisión**");st.json(t.get("decision"));st.markdown("**Estado y hechos capturados**");st.json(t.get("state_after"));ev=t.get("evidence") or {};st.markdown("**Evidencia**");st.json(ev.get("counts") or {});st.markdown("**Fuentes citables**");st.json(ev.get("citable") or []);st.markdown("**Respuesta propuesta**");st.markdown((t.get("answer") or {}).get("text") or "Sin respuesta");st.markdown("**Evaluación técnica y funcional**");st.json(t.get("functional_checkpoint"));
  with st.expander("Documentos recuperados y motivos"):st.json(ev.get("retrieved") or [])
 st.download_button("Descargar resultado JSON",json.dumps(r,ensure_ascii=False,indent=2),file_name=f"agent_core_v2_{r.get('scenario_id')}.json",mime="application/json")
