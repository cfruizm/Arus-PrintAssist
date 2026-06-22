# streamlit_app.py
# Main Streamlit entrypoint for Arus PrintAssist

import streamlit as st

from app.config import (
    APP_TITLE,
    APP_SUBTITLE,
    PAGE_ICON,
    PAGE_LAYOUT,
    SIDEBAR_TITLE,
)

from app.session_state import ChatSessionState

# The fallback keeps the app loadable while the backend module is still incomplete.
try:
    from app.backend import (
        create_chat_session_state,
        route_user_message,
        finalize_escalation_case,
        reset_chat_session_state,
        backend_is_ready,
    )
except Exception:
    create_chat_session_state = None
    route_user_message = None
    finalize_escalation_case = None
    reset_chat_session_state = None

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

# Extra protection in case an old session survives a code update
if getattr(st.session_state.chat_state, "incident_state", None) is None:
    try:
        from app.backend import IncidentState
        st.session_state.chat_state.incident_state = IncidentState()
    except Exception:
        pass

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": (
                "Hola, soy Arus PrintAssist. "
                "Puedo ayudarte con documentación técnica, troubleshooting básico "
                "y recopilación de información para escalamiento."
            ),
        }
    ]

# ---------------------------------------------------------------------------
st.markdown(
    """
**Arus PrintAssist** puede ayudarte con documentación técnica, troubleshooting básico, procedimientos del servicio de impresión y recopilación de información para escalamiento.

**Ten en cuenta:**
- Responde con base en la documentación disponible.
- Puede dar respuestas parciales si una consulta no está bien cubierta por la base documental.
- En casos críticos o ambiguos, se recomienda validar la información o escalar el caso.
"""
)

# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header(SIDEBAR_TITLE)

    mode = getattr(st.session_state.chat_state, "mode", "normal")
    st.write(f"**Modo actual:** {mode}")

    if backend_is_ready():
        st.success("Backend ready")
    else:
        st.warning("Backend not ready")
    
    # Temporary debug panel
    with st.expander("Debug query diagnostics"):
        debug_query = st.text_input(
            "Consulta para depuración",
            value="¿Que requerimientos son necesarios para instalar HP SDS monitor?"
        )

        if st.button("Ejecutar diagnóstico"):
            try:
                from app.backend import debug_query_diagnostics
                debug_result = debug_query_diagnostics(debug_query)
                st.json(debug_result)
            except Exception as e:
                st.error(f"No fue posible ejecutar el diagnóstico: {e}")

        try:
            from app.backend import get_backend_status
            status = get_backend_status()
            st.json(status)
        except Exception as e:
            st.error(f"No fue posible obtener el estado del backend: {e}")

    if st.button("Nueva conversación"):
        if reset_chat_session_state is not None:
            st.session_state.chat_state = reset_chat_session_state()
        else:
            st.session_state.chat_state = ChatSessionState()

        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": (
                    "La sesión fue reiniciada. "
                    "Puedes comenzar con una nueva consulta."
                ),
            }
        ]
        st.rerun()

    if backend_is_ready() and mode == "escalation":
        if st.button("Finalizar y exportar caso"):
            result = finalize_escalation_case(st.session_state.chat_state)
    
            st.success("Caso persistido correctamente.")
    
            exported_file_path = result.get("exported_file")
    
            if exported_file_path:
                try:
                    with open(exported_file_path, "r", encoding="utf-8") as f:
                        exported_text = f.read()
    
                    file_name = exported_file_path.split("/")[-1]
    
                    st.text_area(
                        "Resumen exportado",
                        exported_text,
                        height=250
                    )
                    
                    st.download_button(
                        label="Descargar resumen del caso (.txt)",
                        data=exported_text,
                        file_name=file_name,
                        mime="text/plain"
                    )
    
                    with st.expander("Ver detalle del archivo exportado"):
                        st.json(result)
    
                except Exception as e:
                    st.error(f"No fue posible preparar la descarga del archivo: {e}")
            else:
                st.warning("No se encontró la ruta del archivo exportado.")
    with st.expander("Guía de uso del asistente", expanded=False):

st.markdown(
        """
### ¿Qué es Arus PrintAssist?
Arus PrintAssist es un asistente especializado en soporte de primer nivel para servicios de impresión.  
Puede ayudarte con consultas sobre software de impresión, herramientas del servicio, procedimientos operativos, troubleshooting básico y recopilación de información para escalamiento.

### ¿Qué puede hacer?
- Responder preguntas conceptuales sobre herramientas y soluciones del servicio de impresión.
- Consultar requerimientos, componentes y características de algunos productos soportados.
- Orientar procedimientos operativos y configuraciones básicas cuando exista soporte documental.
- Brindar apoyo en troubleshooting inicial de incidentes relacionados con impresión.
- Guiar la recolección de información para escalamiento de casos.
- Responder usando la base documental disponible e indicar las fuentes consultadas.

### Limitaciones
- Las respuestas se generan con base en la documentación cargada en la base de conocimiento.
- Si la documentación disponible no cubre bien una consulta, la respuesta puede ser parcial, incompleta o conservadora.
- El asistente no reemplaza la validación técnica humana en casos críticos, ambiguos o de alto impacto.
- Algunas respuestas pueden contener errores, omisiones o interpretaciones imperfectas de la documentación.

### Ejemplos de preguntas recomendadas
- ¿Qué es HP Web Jetadmin?
- ¿Qué requerimientos son necesarios para instalar HP SDS Monitor?
- ¿Cómo reiniciar manualmente el servicio de HP Web Jetadmin?
- ¿Qué debo hacer si los trabajos desaparecen en PaperCut MF?
- ¿Cuáles son los componentes de la solución HP Access Control?
- ¿Cómo realizar el trámite de garantía de los suministros de impresión?
- ¿Qué debo tener en cuenta para una arquitectura de seguridad en nube de GAV Tracking?

### Aviso
Este asistente puede cometer errores u omisiones.  
Si la consulta implica configuraciones críticas, procedimientos de alto impacto, cambios en seguridad o decisiones operativas sensibles, se recomienda validar la respuesta con documentación adicional o escalar el caso cuando corresponda.
"""
    )
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
    st.session_state.chat_messages.append(
        {
            "role": "user",
            "content": user_prompt,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_prompt)

    if backend_is_ready() and route_user_message is not None:
        bot_response = route_user_message(
            user_prompt,
            st.session_state.chat_state,
        )
    else:
        bot_response = (
            "El frontend ya está listo, pero el backend todavía no está conectado "
            "en el proyecto Streamlit. En el siguiente paso integraremos "
            "route_user_message(...) y el resto de funciones."
        )

    st.session_state.chat_messages.append(
        {
            "role": "assistant",
            "content": bot_response,
        }
    )

    with st.chat_message("assistant"):
        st.markdown(bot_response)
