from __future__ import annotations
import json

TECHNICAL_INTENTS = {"conceptual", "procedural", "troubleshooting", "requirements", "architecture", "warranty"}

REPAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "conversation_act": {"type": "string", "enum": ["technical_request", "clarification", "capability", "social", "farewell", "escalation", "cancel", "attempt", "attempt_result"]},
        "intent": {"type": "string", "enum": ["conceptual", "procedural", "troubleshooting", "requirements", "architecture", "warranty", "escalation", "cancel", "unknown"]},
        "topic_relation": {"type": "string", "enum": ["same_topic", "new_topic", "return_to_previous", "independent_question", "unknown"]},
        "requires_documents": {"type": "boolean"},
        "confidence": {"type": "number"},
        "reasoning_summary": {"type": "string"}
    },
    "required": ["conversation_act", "intent", "topic_relation", "requires_documents", "confidence", "reasoning_summary"]
}

def contract_is_suspicious(raw: dict) -> bool:
    act = str(raw.get("conversation_act") or "")
    intent = str(raw.get("intent") or "unknown")
    docs = bool(raw.get("requires_documents", False))
    summary = str(raw.get("reasoning_summary") or "").lower()
    if act == "clarification" and intent in TECHNICAL_INTENTS and docs:
        return True
    if act == "technical_request" and intent == "unknown":
        return True
    if intent in TECHNICAL_INTENTS and any(x in summary for x in ("clarification is appropriate", "clarification is needed")) and docs:
        return True
    return False

def repair_contract(gateway, message: str, state, raw: dict):
    from app.llm_gateway.models import LLMRequest
    payload = {
        "current_message": message,
        "active_context": state.to_dict(),
        "candidate_contract": raw,
        "task": "Reclassify the current user need independently from the previous turn. Preserve context only to resolve omitted subjects. A clear definition/purpose question is conceptual; a how-to is procedural; prerequisites or compatibility are requirements; a reported failure is troubleshooting. Use clarification only if no actionable technical need can be identified."
    }
    result = gateway.complete(LLMRequest(
        [{"role":"system","content":"Repair an inconsistent conversation contract. Return compact JSON only. Do not add entities or facts."},
         {"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],
        "agent_core_v2_contract_repair", 180, 0.0, REPAIR_SCHEMA))
    if not result.ok:
        return None, {"used": True, "ok": False, "reason": "provider_error"}
    try:
        repaired = json.loads(str(result.text).strip())
    except Exception:
        return None, {"used": True, "ok": False, "reason": "invalid_json"}
    if contract_is_suspicious(repaired):
        return None, {"used": True, "ok": False, "reason": "still_inconsistent"}
    return repaired, {"used": True, "ok": True, "reason": "semantic_reclassification"}
