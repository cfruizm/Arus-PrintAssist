import json
from pathlib import Path
import streamlit as st
from app.agent_core_v2.real_lab import run_real_scenario
st.set_page_config(page_title="Agent Core v2 Real Lab",layout="wide")
st.title("Agent Core v2, Fase 2B: laboratorio real")
st.caption("Ejecuta Qwen, domain_registry, retrieval y documentos reales. No modifica el chat productivo.")
scenarios=json.loads(Path("tools/agent_core_v2/real_lab_scenarios.json").read_text(encoding="utf-8"));options={f"{x['name']} ({x['id']})":x for x in scenarios};selected=options[st.selectbox("Escenario",list(options))];st.code("\n".join(selected["messages"]),language="text");st.warning("Cada ejecución consume créditos. Ejecuta un escenario una sola vez.")
if st.button("Ejecutar escenario real",type="primary"):
 with st.spinner("Interpretando, recuperando evidencia y validando..."):st.session_state["agent_core_v2_real_lab_last_result"]=run_real_scenario(selected,st.secrets,st.session_state)
r=st.session_state.get("agent_core_v2_real_lab_last_result")
if r:
 if r.get("status")=="ok":st.success("Ejecución completada")
 else:
  st.error("La ejecución se detuvo antes de completar el escenario")
  d=r.get("error_diagnostic") or {};st.subheader(d.get("title") or "Detalle del error");st.write(d.get("explanation") or r.get("error"));c1,c2=st.columns(2);c1.info(f"Etapa: {d.get('stage','No identificada')}");c2.info(f"Motivo de finalización: {d.get('finish_reason') or 'No disponible'}");st.markdown("**Qué hacer ahora**");st.write(d.get("recommended_action") or "Descarga el JSON para revisar el diagnóstico.")
  with st.expander("Detalle técnico"):
   st.code(d.get("technical_error") or r.get("error") or "Sin detalle",language="text")
   if d.get("partial_model_output"):st.markdown("**Salida parcial de Qwen**");st.code(d["partial_model_output"],language="json")
 a,b,c,dcol=st.columns(4);a.metric("Estado",r.get("status"));b.metric("Checkpoint",str(r.get("checkpoint_passed")));c.metric("Llamadas",r.get("usage",{}).get("calls",0));dcol.metric("Tokens",r.get("usage",{}).get("total_tokens",0))
 for i,t in enumerate(r.get("turns") or [],1):
  st.subheader(f"Turno {i}");st.markdown("**Decisión canónica**");st.json(t.get("decision"));st.markdown("**Estado resultante**");st.json(t.get("state_after"));e=t.get("evidence") or {};st.markdown("**Conteos de evidencia**");st.json(e.get("counts") or {});st.markdown("**Fuentes citables**");st.json(e.get("citable") or []);st.markdown("**Respuesta propuesta**");st.write((t.get("answer") or {}).get("text") or "Sin respuesta");st.markdown("**Checkpoint del turno**");st.json(t.get("checkpoint"));
  with st.expander("Todos los documentos y motivos de rechazo"):st.json(e.get("retrieved") or [])
 payload=json.dumps(r,ensure_ascii=False,indent=2);st.download_button("Descargar resultado JSON",payload,file_name=f"agent_core_v2_{r.get('scenario_id')}.json",mime="application/json")
