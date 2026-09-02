import json
from pathlib import Path
import streamlit as st
from app.agent_core_v2.real_lab import run_real_scenario

st.set_page_config(page_title="Agent Core v2 Real Lab",layout="wide")
st.title("Agent Core v2, Fase 2B: laboratorio real")
st.caption("Ejecuta Qwen, domain_registry, retrieval y documentos reales. No modifica el chat productivo.")
path=Path("tools/agent_core_v2/real_lab_scenarios.json")
scenarios=json.loads(path.read_text(encoding="utf-8"))
options={f"{x['name']} ({x['id']})":x for x in scenarios}
selected=options[st.selectbox("Escenario",list(options))]
st.code("\n".join(selected["messages"]),language="text")
st.warning("Cada ejecución puede realizar una llamada de interpretación y, si corresponde, una llamada de respuesta. Ejecuta un escenario una sola vez.")
if st.button("Ejecutar escenario real",type="primary"):
    with st.spinner("Ejecutando Agent Core v2..."):
        result=run_real_scenario(selected,st.secrets,st.session_state)
    st.session_state["agent_core_v2_real_lab_last_result"]=result
result=st.session_state.get("agent_core_v2_real_lab_last_result")
if result:
    st.success("Ejecución finalizada" if result.get("status")=="ok" else "Ejecución con error")
    a,b,c,d=st.columns(4)
    a.metric("Estado",result.get("status"));b.metric("Checkpoint",str(result.get("checkpoint_passed")));c.metric("Llamadas",result.get("usage",{}).get("calls",0));d.metric("Tokens",result.get("usage",{}).get("total_tokens",0))
    for i,turn in enumerate(result.get("turns") or [],1):
        st.subheader(f"Turno {i}")
        st.markdown("**Decisión canónica**");st.json(turn.get("decision"))
        st.markdown("**Estado resultante**");st.json(turn.get("state_after"))
        ev=turn.get("evidence") or {};st.markdown("**Conteos de evidencia**");st.json(ev.get("counts") or {})
        with st.expander("Documentos recuperados y motivos"):
            st.json(ev.get("retrieved") or [])
        st.markdown("**Fuentes citables**");st.json(ev.get("citable") or [])
        st.markdown("**Respuesta propuesta**");st.write((turn.get("answer") or {}).get("text") or "Sin respuesta")
        st.markdown("**Checkpoint del turno**");st.json(turn.get("checkpoint"))
    payload=json.dumps(result,ensure_ascii=False,indent=2)
    st.download_button("Descargar resultado JSON",payload,file_name=f"agent_core_v2_{result.get('scenario_id')}.json",mime="application/json")
