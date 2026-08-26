from __future__ import annotations
import os

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

# All new-core production and shadow capabilities are disabled by default.
AGENT_CORE_V1_ENABLED = env_bool("AGENT_CORE_V1_ENABLED", False)
AGENT_CORE_V1_SHADOW_ENABLED = env_bool("AGENT_CORE_V1_SHADOW_ENABLED", False)
AGENT_CORE_V1_SHADOW_WRITE_REPORT = env_bool("AGENT_CORE_V1_SHADOW_WRITE_REPORT", False)
