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
            st.json(result)


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
