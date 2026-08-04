# streamlit_app.py
# Main Streamlit entrypoint for Arus PrintAssist

from __future__ import annotations

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
# Default is False to keep the demo clean. Enable in Streamlit secrets with:
# DEBUG_UI = true
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
        debug_metadata_search,
    )
except Exception as e:
    BACKEND_IMPORT_ERROR = e

    IncidentState = None
    create_chat_session_state = None
    route_user_message = None
    finalize_escalation_case = None
    reset_chat_session_state = None
    get_backend_status = None
    debug_query_diagnostics = None
    debug_metadata_search = None

    def backend_is_ready() -> bool:
        return False

# -----------------------------------------------------------------------------
# Page configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=PAGE_ICON,
    layout=PAGE_LAYOUT,
)

st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

# -----------------------------------------------------------------------------
# Session bootstrap
# -----------------------------------------------------------------------------
if "chat_state" not in st.session_state:
    if create_chat_session_state is not None:
        st.session_state.chat_state = create_chat_session_state()
    else:
        st.session_state.chat_state = ChatSessionState()

# Extra protection in case an old session survives a code update.
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

# Cache this result for the current run to avoid repeated checks in the UI.
BACKEND_READY = backend_is_ready()
CURRENT_MODE = getattr(st.session_state.chat_state, "mode", "normal")

# -----------------------------------------------------------------------------
# Main user guidance block
# -----------------------------------------------------------------------------
st.markdown(
    """
**Arus PrintAssist** puede ayudarte con documentación técnica, troubleshooting básico,
procedimientos del servicio de impresión y recopilación de información para escalamiento.

**Ten en cuenta:** responde con base en la documentación disponible. En casos críticos,
ambiguos o de alto impacto, valida la información o escala el caso cuando corresponda.
"""
)

with st.expander("Guía de uso del asistente", expanded=False):
    st.markdown(
        """
### ¿Qué puede hacer?
- Responder preguntas conceptuales sobre herramientas y soluciones del servicio de impresión.
- Consultar requerimientos, componentes y características de productos soportados.
- Orientar procedimientos operativos cuando exista soporte documental.
- Apoyar troubleshooting inicial de incidentes relacionados con impresión.
- Guiar la recolección de información para escalamiento de casos.
- Responder usando la base documental disponible e indicar las fuentes consultadas.

### Ejemplos de preguntas
- ¿Qué es HP Access Control?
- ¿Qué requerimientos son necesarios para instalar HP SDS Monitor?
- ¿Qué debo hacer si la cola de impresión está bloqueada?
- ¿Cómo consultar y asignar PIN en Print Evolve?
- ¿Cómo realizar el trámite de garantía de los suministros de impresión?
- Ya reinicié el servicio y sigue fallando, necesito escalar el caso.

### Limitaciones
El asistente puede entregar respuestas parciales si la documentación disponible no cubre bien la consulta.
No reemplaza la validación técnica humana en configuraciones críticas, cambios de seguridad o incidentes de alto impacto.
"""
    )

# -----------------------------------------------------------------------------
# Sidebar: essential controls only
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header(SIDEBAR_TITLE)

    if st.button("Nueva conversación"):
        if reset_chat_session_state is not None:
            st.session_state.chat_state = reset_chat_session_state()
        else:
            st.session_state.chat_state = ChatSessionState()

        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": "La sesión fue reiniciada. Puedes comenzar con una nueva consulta.",
            }
        ]
        st.rerun()

    if not BACKEND_READY:
        st.warning(
            "El servicio de respuestas no está disponible temporalmente. "
            "Intenta nuevamente más tarde."
        )

    if BACKEND_READY and CURRENT_MODE == "escalation" and finalize_escalation_case is not None:
        if st.button("Finalizar y exportar caso"):
            try:
                result = finalize_escalation_case(st.session_state.chat_state)
                st.success("Caso persistido correctamente.")

                exported_file_path = result.get("exported_file")
                if exported_file_path:
                    with open(exported_file_path, "r", encoding="utf-8") as f:
                        exported_text = f.read()

                    file_name = exported_file_path.split("/")[-1]
                    st.text_area("Resumen exportado", exported_text, height=220)
                    st.download_button(
                        label="Descargar resumen del caso (.txt)",
                        data=exported_text,
                        file_name=file_name,
                        mime="text/plain",
                    )
                else:
                    st.warning("No se encontró la ruta del archivo exportado.")
            except Exception as e:
                st.error(f"No fue posible exportar el caso: {e}")

    # -------------------------------------------------------------------------
    # Optional technical debug panel. Hidden by default.
    # -------------------------------------------------------------------------
    if DEBUG_UI:
        with st.expander("Diagnóstico técnico", expanded=False):
            st.caption("Úsalo solo para pruebas. Algunas acciones no llaman al LLM; el chat normal sí puede consumir créditos.")

            if BACKEND_IMPORT_ERROR is not None:
                st.error("Error importando app.backend")
                st.exception(BACKEND_IMPORT_ERROR)

                if isinstance(BACKEND_IMPORT_ERROR, SyntaxError):
                    st.write("Archivo:", BACKEND_IMPORT_ERROR.filename)
                    st.write("Línea:", BACKEND_IMPORT_ERROR.lineno)
                    st.write("Offset:", BACKEND_IMPORT_ERROR.offset)
                    st.write("Mensaje:", BACKEND_IMPORT_ERROR.msg)
                    if BACKEND_IMPORT_ERROR.text:
                        st.code(BACKEND_IMPORT_ERROR.text, language="python")

            st.write(f"**Modo actual:** {CURRENT_MODE}")
            st.write("**Backend:**", "ready" if BACKEND_READY else "not ready")

            if get_backend_status is not None and st.button("Ver estado backend"):
                try:
                    st.json(get_backend_status())
                except Exception as e:
                    st.error(f"Error consultando backend: {e}")

            if "last_turn_diagnostics" in st.session_state:
                with st.expander("Último turno observado", expanded=False):
                    st.json(st.session_state["last_turn_diagnostics"])

            if "last_llm_diagnostics" in st.session_state:
                with st.expander("Última llamada LLM", expanded=False):
                    st.json(st.session_state["last_llm_diagnostics"])

            st.divider()
            st.markdown("**Debug retrieval, no consume LLM**")
            debug_query = st.text_area(
                "Consulta para debug retrieval",
                value="¿Qué es HP Access Control?",
                height=90,
            )
            if st.button("Ejecutar debug retrieval"):
                if debug_query_diagnostics is None:
                    st.error("debug_query_diagnostics no está disponible.")
                else:
                    try:
                        st.json(debug_query_diagnostics(debug_query))
                    except Exception as e:
                        st.error(f"Error ejecutando debug retrieval: {e}")

            st.divider()
            st.markdown("**Buscar metadata/vectorstore, no consume LLM**")
            metadata_search_term = st.text_input(
                "Término de búsqueda",
                value="HP Access Control",
            )
            if st.button("Buscar metadata"):
                if debug_metadata_search is None:
                    st.error("debug_metadata_search no está disponible.")
                else:
                    try:
                        st.json(debug_metadata_search(metadata_search_term))
                    except Exception as e:
                        st.error(f"Error buscando metadata: {e}")

# -----------------------------------------------------------------------------
# Render chat history
# -----------------------------------------------------------------------------
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -----------------------------------------------------------------------------
# Chat input
# -----------------------------------------------------------------------------
user_prompt = st.chat_input("Describe tu consulta o incidente de impresión...")

if user_prompt:
    st.session_state.chat_messages.append({"role": "user", "content": user_prompt})

    with st.chat_message("user"):
        st.markdown(user_prompt)

    if BACKEND_READY and route_user_message is not None:
        try:
            bot_response = route_user_message(user_prompt, st.session_state.chat_state)
        except Exception as e:
            bot_response = (
                "Se presentó un error procesando tu solicitud. "
                "Si el problema persiste, revisa el diagnóstico técnico o intenta nuevamente."
            )
            if DEBUG_UI:
                st.exception(e)
    else:
        bot_response = (
            "El servicio de respuestas no está disponible temporalmente. "
            "Por favor intenta nuevamente más tarde."
        )

    st.session_state.chat_messages.append({"role": "assistant", "content": bot_response})

    with st.chat_message("assistant"):
        st.markdown(bot_response)
