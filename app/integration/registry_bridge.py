from __future__ import annotations
from app.domain_registry_v1 import PRODUCT_ENTITY_REGISTRY, PROCESS_ENTITY_REGISTRY

def get_candidate_registries() -> tuple[dict, dict]:
    """Return the expanded candidate registries without overwriting app.domain_registry."""
    return PRODUCT_ENTITY_REGISTRY, PROCESS_ENTITY_REGISTRY
