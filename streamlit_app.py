# streamlit_app.py
# Main Streamlit entrypoint for Arus PrintAssist

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import html
import os
import resource

import streamlit as st

from app.config import (
    APP_TITLE,
    APP_SUBTITLE,
    PAGE_ICON,
    PAGE_LAYOUT,
    SIDEBAR_TITLE,
)
from app.session_state import ChatSessionState


# -----------------------------------------------------------------------------
# Debug mode
# -----------------------------------------------------------------------------
try:
    DEBUG_UI = bool(st.secrets.get("DEBUG_UI", False))
except Exception:
    DEBUG_UI = False


# -----------------------------------------------------------------------------
# Backend imports
# -----------------------------------------------------------------------------
BACKEND_IMPORT_ERROR = None

try:
    from app.backend import (
        IncidentState,
        create_chat_session_state,
        route_user_message,
        finalize_escalation_case,
        reset_chat_session_state,
        backend_is_ready,
        get_backend_status,
        debug_query_diagnostics,
        summarize_turn_observability,
    )

    try:
        from app.backend import debug_metadata_search
    except Exception:
        debug_metadata_search = None

except Exception as exc:
    BACKEND_IMPORT_ERROR = exc

    IncidentState = None
    create_chat_session_state = None
    route_user_message = None
    finalize_escalation_case = None
    reset_chat_session_state = None
    get_backend_status = None
    debug_query_diagnostics = None
    debug_metadata_search = None
    summarize_turn_observability = None

    def backend_is_ready() -> bool:
        return False


# -----------------------------------------------------------------------------
# Page configuration and lightweight visual polish
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=PAGE_ICON,
    layout=PAGE_LAYOUT,
)

st.markdown(
    """
<style>
    .block-container {padding-top: 1.8rem; padding-bottom: 2rem;}
    [data-testid="stSidebar"] {border-right: 1px solid rgba(49, 51, 63, 0.12);}
    .ap-status {
        display: inline-flex;
        align-items: center;
        gap: .45rem;
        padding: .28rem .65rem;
        border-radius: 999px;
        font-size: .82rem;
        font-weight: 600;
        margin-bottom: .65rem;
    }
    .ap-status-ready {background: #e8f5e9; color: #1b5e20;}
    .ap-status-collecting {background: #fff3e0; color: #8a4b08;}
    .ap-status-completed {background: #e8eaf6; color: #283593;}
    .ap-card {
        padding: .9rem 1rem;
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: .65rem;
        background: rgba(248, 249, 251, .65);
        margin-bottom: .8rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title(APP_TITLE)
st.caption(APP_SUBTITLE)


# -----------------------------------------------------------------------------
# Session bootstrap
# -----------------------------------------------------------------------------
def build_new_chat_state():
    if create_chat_session_state is not None:
        return create_chat_session_state()
    return ChatSessionState()


if "chat_state" not in st.session_state:
    st.session_state.chat_state = build_new_chat_state()

if getattr(st.session_state.chat_state, "incident_state", None) is None:
    if IncidentState is not None:
        st.session_state.chat_state.incident_state = IncidentState()

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": "Hola, soy Arus PrintAssist. ¿Con qué puedo ayudarte hoy?",
        }
    ]

if "prepared_export_text" not in st.session_state:
    st.session_state.prepared_export_text = None

if "prepared_export_name" not in st.session_state:
    st.session_state.prepared_export_name = None

if "last_ui_error" not in st.session_state:
    st.session_state.last_ui_error = None

# Do not call backend_is_ready() here. That call loads the embedding model and
# vectorstore at page startup. Keeping startup lazy reduces memory pressure and
# allows deterministic help/intake routes to work without loading ML resources.
BACKEND_AVAILABLE = BACKEND_IMPORT_ERROR is None and route_user_message is not None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def current_workflow_state() -> str:
    return getattr(st.session_state.chat_state, "escalation_workflow_state", "normal")


def current_mode() -> str:
    return getattr(st.session_state.chat_state, "mode", "normal")


def current_resource_usage_mb() -> float:
    """Return process peak RSS in MB without adding a third-party dependency."""
    try:
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KB. macOS reports bytes, but Streamlit Cloud is Linux.
        return round(value / 1024, 1)
    except Exception:
        return 0.0


def prepare_export_from_state(force_finalize: bool = False) -> tuple[str | None, str | None]:
    """Prepare a durable browser download from backend state.

    The exported text is copied into st.session_state, so a Streamlit rerun or
    a mode change does not make the download disappear.
    """
    state = st.session_state.chat_state
    summary = getattr(state, "last_escalation_summary", None)
    exported_path = getattr(state, "last_escalation_exported_file", None)

    if force_finalize and finalize_escalation_case is not None and not summary:
        result = finalize_escalation_case(state)
        exported_path = result.get("exported_file")

    exported_text = None
    if summary:
        exported_text = str(summary).strip()
    elif exported_path and Path(exported_path).exists():
        exported_text = Path(exported_path).read_text(encoding="utf-8")
    elif getattr(state, "incident_state", None) is not None:
        # Compatibility fallback for a pre-v9 session. Avoid exporting an empty case.
        incident = state.incident_state
        values = [
            getattr(incident, "software_involved", None),
            getattr(incident, "error_description", None),
            getattr(incident, "printer_data", None),
        ]
        if any(values) and force_finalize and finalize_escalation_case is not None:
            result = finalize_escalation_case(state)
            exported_path = result.get("exported_file")
            if exported_path and Path(exported_path).exists():
                exported_text = Path(exported_path).read_text(encoding="utf-8")

    if not exported_text:
        return None, None

    file_name = (
        Path(exported_path).name
        if exported_path
        else f"incident_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    st.session_state.prepared_export_text = exported_text
    st.session_state.prepared_export_name = file_name
    return exported_text, file_name


def sync_completed_export():
    """Automatically expose a download after the backend completes a case."""
    if st.session_state.prepared_export_text:
        return
    state = st.session_state.chat_state
    if getattr(state, "last_escalation_summary", None):
        prepare_export_from_state(force_finalize=False)


def render_status_badge():
    workflow = current_workflow_state()
    if workflow == "escalation_collecting" or current_mode() == "escalation":
        label = "Escalamiento en recopilación"
        css_class = "ap-status-collecting"
    elif workflow == "escalation_completed":
        label = "Escalamiento completado"
        css_class = "ap-status-completed"
    else:
        label = "Asistente disponible"
        css_class = "ap-status-ready"

    st.markdown(
        f'<div class="ap-status {css_class}">● {html.escape(label)}</div>',
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Main guidance
# -----------------------------------------------------------------------------
render_status_badge()

st.markdown(
    """
**Arus PrintAssist** ofrece soporte documental y orientación de primer nivel para
servicios de impresión, procedimientos técnicos y preparación de escalamientos.

**Alcance:** las respuestas se fundamentan en la documentación disponible. Para
cambios críticos, seguridad o incidentes de alto impacto, valida la información
antes de ejecutarla.
"""
)

with st.expander("Guía de uso del asistente", expanded=False):
    st.markdown(
        """
### Capacidades
- Explicar herramientas y soluciones del servicio de impresión.
- Consultar requisitos, componentes y características documentadas.
- Orientar procedimientos operativos y troubleshooting inicial.
- Preparar y exportar un resumen técnico para escalamiento.
- Mostrar las fuentes documentales utilizadas.

### Para obtener mejores resultados
Incluye el producto o herramienta, el síntoma, el equipo o cola afectada y las
validaciones realizadas. También puedes escribir **¿Qué puedes hacer?** para ver
las opciones disponibles.

### Ejemplos
- ¿Qué requisitos necesita HP SDS Monitor?
- ¿Qué debo revisar si los trabajos quedan retenidos en PaperCut?
- ¿Cómo se instala el administrador de GAV Tracking?
- Ya reinicié el servicio y sigue fallando; necesito escalar el caso.
"""
    )


# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------
sync_completed_export()

with st.sidebar:
    st.header(SIDEBAR_TITLE)

    if st.button("Nueva conversación", use_container_width=True):
        st.session_state.chat_state = build_new_chat_state()
        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": "La sesión fue reiniciada. Puedes comenzar con una nueva consulta.",
            }
        ]
        st.session_state.prepared_export_text = None
        st.session_state.prepared_export_name = None
        st.session_state.last_ui_error = None
        st.rerun()

    workflow = current_workflow_state()
    active_escalation = workflow == "escalation_collecting" or current_mode() == "escalation"

    if active_escalation:
        st.caption("Caso en recopilación")
        if st.button("Finalizar y preparar exportación", use_container_width=True):
            try:
                export_text, export_name = prepare_export_from_state(force_finalize=True)
                if export_text:
                    st.success("Resumen preparado para descarga.")
                else:
                    st.warning(
                        "Aún no hay información suficiente para exportar. "
                        "Completa los datos solicitados en el chat."
                    )
            except Exception as exc:
                st.session_state.last_ui_error = str(exc)
                st.error("No fue posible preparar la exportación.")

    if st.session_state.prepared_export_text:
        st.divider()
        st.markdown("**Último resumen de escalamiento**")
        st.download_button(
            label="Descargar resumen (.txt)",
            data=st.session_state.prepared_export_text,
            file_name=st.session_state.prepared_export_name or "incident_summary.txt",
            mime="text/plain; charset=utf-8",
            use_container_width=True,
            key="download_latest_incident_summary",
        )
        with st.expander("Vista previa del resumen", expanded=False):
            st.text_area(
                "Contenido exportable",
                st.session_state.prepared_export_text,
                height=240,
                disabled=True,
                label_visibility="collapsed",
            )

    if not BACKEND_AVAILABLE:
        st.error("El backend no está disponible. Revisa el diagnóstico técnico.")

    if DEBUG_UI:
        with st.expander("Diagnóstico técnico", expanded=False):
            st.caption(
                "Las consultas de debug no llaman al LLM. Las consultas normales sí pueden consumir créditos."
            )
            st.metric("Pico de memoria del proceso", f"{current_resource_usage_mb()} MB")

            if BACKEND_IMPORT_ERROR is not None:
                st.error("Error importando app.backend")
                st.exception(BACKEND_IMPORT_ERROR)

            st.write("**Modo:**", current_mode())
            st.write("**Flujo:**", current_workflow_state())
            st.write("**Backend importado:**", BACKEND_AVAILABLE)

            if get_backend_status is not None and st.button("Ver estado backend"):
                try:
                    with st.spinner("Verificando modelos y vectorstore..."):
                        st.json(get_backend_status())
                except Exception as exc:
                    st.error(f"Error consultando backend: {exc}")

            if "last_turn_diagnostics" in st.session_state:
                with st.expander("Último turno observado", expanded=False):
                    st.json(st.session_state["last_turn_diagnostics"])

            if summarize_turn_observability is not None and st.button("Ver observabilidad"):
                try:
                    st.json(summarize_turn_observability())
                except Exception as exc:
                    st.error(f"No fue posible calcular la observabilidad: {exc}")

            if "last_llm_diagnostics" in st.session_state:
                with st.expander("Última llamada LLM", expanded=False):
                    st.json(st.session_state["last_llm_diagnostics"])

            st.divider()
            debug_query = st.text_area(
                "Debug retrieval, no consume LLM",
                value="¿Qué es HP Access Control?",
                height=90,
            )
            if st.button("Ejecutar debug retrieval"):
                if debug_query_diagnostics is None:
                    st.error("debug_query_diagnostics no está disponible.")
                else:
                    try:
                        st.json(debug_query_diagnostics(debug_query))
                    except Exception as exc:
                        st.error(f"Error ejecutando debug retrieval: {exc}")

            if debug_metadata_search is not None:
                st.divider()
                metadata_term = st.text_input("Buscar metadata", value="HP Access Control")
                if st.button("Ejecutar búsqueda de metadata"):
                    try:
                        st.json(debug_metadata_search(metadata_term))
                    except Exception as exc:
                        st.error(f"Error buscando metadata: {exc}")

            if st.session_state.last_ui_error:
                st.divider()
                st.error(f"Último error de interfaz: {st.session_state.last_ui_error}")


# -----------------------------------------------------------------------------
# Render history
# -----------------------------------------------------------------------------
for message in st.session_state.chat_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# -----------------------------------------------------------------------------
# Chat input
# -----------------------------------------------------------------------------
user_prompt = st.chat_input("Describe tu consulta o incidente de impresión...")

if user_prompt:
    st.session_state.chat_messages.append({"role": "user", "content": user_prompt})

    with st.chat_message("user"):
        st.markdown(user_prompt)

    if BACKEND_AVAILABLE:
        try:
            with st.spinner("Consultando la base documental..."):
                bot_response = route_user_message(user_prompt, st.session_state.chat_state)
        except Exception as exc:
            st.session_state.last_ui_error = str(exc)
            bot_response = (
                "Se presentó un error procesando la solicitud. "
                "La sesión continúa activa; intenta nuevamente o revisa el diagnóstico técnico."
            )
            if DEBUG_UI:
                st.exception(exc)
    else:
        bot_response = (
            "El servicio de respuestas no está disponible temporalmente. "
            "Por favor intenta nuevamente más tarde."
        )

    st.session_state.chat_messages.append({"role": "assistant", "content": bot_response})

    # If the backend completed an escalation during this turn, preserve its
    # summary as browser-download data before the next Streamlit rerun.
    sync_completed_export()

    with st.chat_message("assistant"):
        st.markdown(bot_response)
