from __future__ import annotations
from app.integration.feature_flags import (
    AGENT_CORE_V1_ENABLED,
    AGENT_CORE_V1_SHADOW_ENABLED,
    AGENT_CORE_V1_SHADOW_WRITE_REPORT,
)
from app.integration.registry_bridge import get_candidate_registries

def get_stage4a_status() -> dict:
    products, processes = get_candidate_registries()
    return {
        "stage": "4A",
        "installation_ok": True,
        "agent_core_enabled": AGENT_CORE_V1_ENABLED,
        "shadow_enabled": AGENT_CORE_V1_SHADOW_ENABLED,
        "shadow_write_report": AGENT_CORE_V1_SHADOW_WRITE_REPORT,
        "candidate_product_count": len(products),
        "candidate_process_count": len(processes),
        "production_files_modified": False,
        "llm_calls": 0,
    }
