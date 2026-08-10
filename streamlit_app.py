# streamlit_app.py
# Main Streamlit entrypoint for Arus PrintAssist

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import html
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
# Runtime configuration
# -----------------------------------------------------------------------------
try:
    DEBUG_UI = bool(st.secrets.get("DEBUG_UI", False))
except Exception:
    DEBUG_UI = False

PDF_LIBRARY_ROOT = Path("data/knowledge_base_pdfs")
MAX_VISIBLE_PDF_DOWNLOADS = 3
MAX_INLINE_PDF_SIZE_BYTES = 15 * 1024 * 1024


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


# -----------------------------------------------------------------------------
# Page configuration and visual polish
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
        display: inline-flex; align-items: center; gap: .45rem;
        padding: .28rem .65rem; border-radius: 999px;
        font-size: .82rem; font-weight: 600; margin-bottom: .65rem;
    }
    .ap-ready {background: #e8f5e9; color: #1b5e20;}
    .ap-collecting {background: #fff3e0; color: #8a4b08;}
    .ap-completed {background: #e8eaf6; color: #283593;}
    .ap-source-meta {font-size: .85rem; color: #5f6368; margin-bottom: .35rem;}
</style>
""",
    unsafe_allow_html=True,
)

st.title(APP_TITLE)
st.caption(APP_SUBTITLE)


# -----------------------------------------------------------------------------
# Session bootstrap
# -----------------------------------------------------------------------------
def new_chat_state():
    if create_chat_session_state is not None:
        return create_chat_session_state()
    return ChatSessionState()


if "chat_state" not in st.session_state:
    st.session_state.chat_state = new_chat_state()

if getattr(st.session_state.chat_state, "incident_state", None) is None and IncidentState is not None:
    st.session_state.chat_state.incident_state = IncidentState()

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": "Hola, soy Arus PrintAssist. ¿Con qué puedo ayudarte hoy?"}
    ]

if "prepared_export_text" not in st.session_state:
    st.session_state.prepared_export_text = None
if "prepared_export_name" not in st.session_state:
    st.session_state.prepared_export_name = None
if "last_ui_error" not in st.session_state:
    st.session_state.last_ui_error = None

BACKEND_AVAILABLE = BACKEND_IMPORT_ERROR is None and route_user_message is not None


# -----------------------------------------------------------------------------
# UI helpers
# -----------------------------------------------------------------------------
def workflow_state() -> str:
    return getattr(st.session_state.chat_state, "escalation_workflow_state", "normal")


def chat_mode() -> str:
    return getattr(st.session_state.chat_state, "mode", "normal")


def render_status():
    workflow = workflow_state()
    if workflow == "escalation_collecting" or chat_mode() == "escalation":
        label, css = "Escalamiento en recopilación", "ap-collecting"
    elif workflow == "escalation_completed":
        label, css = "Escalamiento completado", "ap-completed"
    else:
        label, css = "Asistente disponible", "ap-ready"
    st.markdown(
        f'<div class="ap-status {css}">● {html.escape(label)}</div>',
        unsafe_allow_html=True,
    )


def peak_memory_mb() -> float:
    try:
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:
        return 0.0


def safe_pdf_path(relative_path: str) -> Path | None:
    """Resolve a metadata path without allowing traversal outside the PDF root."""
    try:
        relative = Path(str(relative_path or ""))
        if relative.is_absolute() or ".." in relative.parts:
            return None
        root = PDF_LIBRARY_ROOT.resolve()
        candidate = (PDF_LIBRARY_ROOT / relative).resolve()
        candidate.relative_to(root)
        return candidate
    except Exception:
        return None


def human_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return "Tamaño no disponible"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def render_pdf_downloads(pdf_sources: list[dict], message_index: int, active: bool):
    """Render at most three PDF controls for the latest sourced response only.

    Older messages keep their textual Fuente(s) block. Avoiding binary reads for
    the full chat history prevents PDF download controls from accumulating RAM.
    """
    sources = (pdf_sources or [])[:MAX_VISIBLE_PDF_DOWNLOADS]
    if not sources:
        return

    if not active:
        st.caption("Los documentos descargables están disponibles en la respuesta más reciente.")
        return

    with st.expander(f"Documentos PDF consultados ({len(sources)})", expanded=False):
        for source_index, source in enumerate(sources):
            file_name = str(source.get("file_name") or "documento.pdf")
            title = str(source.get("title") or Path(file_name).stem)
            pages = [str(value) for value in source.get("page_labels", []) if value is not None]
            path = safe_pdf_path(str(source.get("relative_path") or ""))

            st.markdown(f"**{title}**")
            details = [file_name]
            if pages:
                details.append("Página(s) consultada(s): " + ", ".join(pages))
            if source.get("size_bytes"):
                details.append(human_size(source.get("size_bytes")))
            st.markdown(
                '<div class="ap-source-meta">' + " · ".join(html.escape(item) for item in details) + "</div>",
                unsafe_allow_html=True,
            )

            if not source.get("download_allowed"):
                if source.get("status") == "too_large":
                    st.info("El PDF supera el límite de 15 MB para descarga directa.")
                else:
                    st.info("El archivo original no está disponible para descarga en este entorno.")
            elif path is None or not path.is_file():
                st.info("El archivo original no está disponible para descarga en este entorno.")
            elif path.stat().st_size > MAX_INLINE_PDF_SIZE_BYTES:
                st.info("El PDF supera el límite de 15 MB para descarga directa.")
            else:
                # Read only the latest response's small PDFs. Do not persist bytes
                # in session state and do not cache them.
                try:
                    pdf_bytes = path.read_bytes()
                    st.download_button(
                        label=f"Descargar {file_name}",
                        data=pdf_bytes,
                        file_name=file_name,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"pdf_download_{message_index}_{source_index}",
                    )
                except Exception as exc:
                    st.session_state.last_ui_error = str(exc)
                    st.warning("No fue posible preparar este documento para descarga.")

            if source_index < len(sources) - 1:
                st.divider()


def prepare_escalation_export(force_finalize: bool = False):
    state = st.session_state.chat_state
    summary = getattr(state, "last_escalation_summary", None)
    exported_path = getattr(state, "last_escalation_exported_file", None)

    if force_finalize and finalize_escalation_case is not None and not summary:
        result = finalize_escalation_case(state)
        exported_path = result.get("exported_file")

    text = str(summary).strip() if summary else None
    if not text and exported_path and Path(exported_path).is_file():
        text = Path(exported_path).read_text(encoding="utf-8")

    if not text:
        return None, None

    name = Path(exported_path).name if exported_path else f"incident_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    st.session_state.prepared_export_text = text
    st.session_state.prepared_export_name = name
    return text, name


def sync_escalation_export():
    if st.session_state.prepared_export_text:
        return
    if getattr(st.session_state.chat_state, "last_escalation_summary", None):
        prepare_escalation_export(force_finalize=False)


def latest_assistant_source_index() -> int | None:
    for index in range(len(st.session_state.chat_messages) - 1, -1, -1):
        message = st.session_state.chat_messages[index]
        if message.get("role") == "assistant" and message.get("pdf_sources"):
            return index
    return None


# -----------------------------------------------------------------------------
# Guidance
# -----------------------------------------------------------------------------
render_status()
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
validaciones realizadas. También puedes escribir **¿Qué puedes hacer?**.
"""
    )


# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------
sync_escalation_export()

with st.sidebar:
    st.header(SIDEBAR_TITLE)

    if st.button("Nueva conversación", use_container_width=True):
        st.session_state.chat_state = new_chat_state()
        st.session_state.chat_messages = [
            {"role": "assistant", "content": "La sesión fue reiniciada. Puedes comenzar con una nueva consulta."}
        ]
        st.session_state.prepared_export_text = None
        st.session_state.prepared_export_name = None
        st.session_state.last_ui_error = None
        st.rerun()

    active_escalation = workflow_state() == "escalation_collecting" or chat_mode() == "escalation"
    if active_escalation and st.button("Finalizar y preparar exportación", use_container_width=True):
        try:
            export_text, _ = prepare_escalation_export(force_finalize=True)
            if export_text:
                st.success("Resumen preparado para descarga.")
            else:
                st.warning("Completa los datos solicitados antes de exportar.")
        except Exception as exc:
            st.session_state.last_ui_error = str(exc)
            st.error("No fue posible preparar la exportación.")

    if st.session_state.prepared_export_text:
        st.divider()
        st.markdown("**Último resumen de escalamiento**")
        st.download_button(
            "Descargar resumen (.txt)",
            data=st.session_state.prepared_export_text,
            file_name=st.session_state.prepared_export_name or "incident_summary.txt",
            mime="text/plain; charset=utf-8",
            use_container_width=True,
            key="download_latest_incident_summary",
        )
        with st.expander("Vista previa", expanded=False):
            st.text_area(
                "Resumen",
                st.session_state.prepared_export_text,
                height=220,
                disabled=True,
                label_visibility="collapsed",
            )

    if not BACKEND_AVAILABLE:
        st.error("El backend no está disponible. Revisa el diagnóstico técnico.")

    if DEBUG_UI:
        with st.expander("Diagnóstico técnico", expanded=False):
            st.metric("Pico de memoria del proceso", f"{peak_memory_mb()} MB")
            st.write("**Modo:**", chat_mode())
            st.write("**Flujo:**", workflow_state())
            st.write("**Backend importado:**", BACKEND_AVAILABLE)

            if BACKEND_IMPORT_ERROR is not None:
                st.exception(BACKEND_IMPORT_ERROR)

            if get_backend_status is not None and st.button("Ver estado backend"):
                try:
                    with st.spinner("Verificando modelo y vectorstore..."):
                        st.json(get_backend_status())
                except Exception as exc:
                    st.error(f"Error consultando backend: {exc}")

            if "last_turn_diagnostics" in st.session_state:
                with st.expander("Último turno observado", expanded=False):
                    st.json(st.session_state["last_turn_diagnostics"])

            if summarize_turn_observability is not None and st.button("Ver observabilidad"):
                st.json(summarize_turn_observability())

            debug_query = st.text_area(
                "Debug retrieval, no consume LLM",
                value="¿Qué es HP Access Control?",
                height=90,
            )
            if st.button("Ejecutar debug retrieval") and debug_query_diagnostics is not None:
                st.json(debug_query_diagnostics(debug_query))

            if debug_metadata_search is not None:
                metadata_term = st.text_input("Buscar metadata", value="HP Access Control")
                if st.button("Ejecutar búsqueda de metadata"):
                    st.json(debug_metadata_search(metadata_term))

            if st.session_state.last_ui_error:
                st.error(f"Último error de interfaz: {st.session_state.last_ui_error}")


# -----------------------------------------------------------------------------
# Render chat history and PDF controls
# -----------------------------------------------------------------------------
active_source_index = latest_assistant_source_index()
for message_index, message in enumerate(st.session_state.chat_messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("role") == "assistant" and message.get("pdf_sources"):
            render_pdf_downloads(
                message.get("pdf_sources", []),
                message_index=message_index,
                active=message_index == active_source_index,
            )


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
            pdf_sources = list(st.session_state.get("last_response_pdf_sources", []) or [])[:MAX_VISIBLE_PDF_DOWNLOADS]
        except Exception as exc:
            st.session_state.last_ui_error = str(exc)
            bot_response = (
                "Se presentó un error procesando la solicitud. "
                "La sesión continúa activa; intenta nuevamente o revisa el diagnóstico técnico."
            )
            pdf_sources = []
            if DEBUG_UI:
                st.exception(exc)
    else:
        bot_response = "El servicio de respuestas no está disponible temporalmente. Intenta nuevamente más tarde."
        pdf_sources = []

    assistant_message = {
        "role": "assistant",
        "content": bot_response,
        "pdf_sources": pdf_sources,
    }
    st.session_state.chat_messages.append(assistant_message)
    sync_escalation_export()

    with st.chat_message("assistant"):
        st.markdown(bot_response)
        if pdf_sources:
            render_pdf_downloads(
                pdf_sources,
                message_index=len(st.session_state.chat_messages) - 1,
                active=True,
            )
