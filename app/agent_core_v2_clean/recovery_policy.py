from __future__ import annotations
from typing import Any
RECOVERABLE_PROCEDURAL_GUARDS={"procedural_citation_guard","procedural_evidence_guard"}

def should_recover_with_controlled_knowledge(answer:Any,assessment:dict[str,Any]) -> bool:
    mode=getattr(answer,"mode",None) if not isinstance(answer,dict) else answer.get("mode")
    return mode in RECOVERABLE_PROCEDURAL_GUARDS and bool(assessment.get("internal_knowledge_candidate") or assessment.get("status") in {"partial","insufficient"})

def recovery_diagnostic(previous_mode:str) -> dict[str,Any]:
    return {"attempted":True,"reason":"documented_procedural_validation_failed","previous_mode":previous_mode,"target_mode":"controlled_internal_knowledge"}
