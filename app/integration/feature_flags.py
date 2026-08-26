from __future__ import annotations

import os

try:
    import streamlit as st
except Exception:
    st = None


TRUE_VALUES = {
    "1",
    "true",
    "yes",
    "on",
    "si",
    "sí",
}


def _to_bool(value, default: bool = False) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in TRUE_VALUES


def get_flag(name: str, default: bool = False) -> bool:
    """
    Resolve an Agent Core feature flag.

    Resolution order:
    1. Streamlit Secrets.
    2. Operating-system environment variable.
    3. Default value.

    This allows the same module to work in Streamlit Cloud,
    local execution and isolated tests.
    """

    if st is not None:
        try:
            secret_value = st.secrets.get(name, None)

            if secret_value is not None:
                return _to_bool(secret_value, default)
        except Exception:
            pass

    environment_value = os.getenv(name)

    if environment_value is not None:
        return _to_bool(environment_value, default)

    return default


AGENT_CORE_V1_ENABLED = get_flag(
    "AGENT_CORE_V1_ENABLED",
    False,
)

AGENT_CORE_V1_SHADOW_ENABLED = get_flag(
    "AGENT_CORE_V1_SHADOW_ENABLED",
    False,
)

AGENT_CORE_V1_SHADOW_WRITE_REPORT = get_flag(
    "AGENT_CORE_V1_SHADOW_WRITE_REPORT",
    False,
)
