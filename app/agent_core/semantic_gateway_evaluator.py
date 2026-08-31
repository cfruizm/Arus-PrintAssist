from __future__ import annotations
import json, re, time
from app.agent_core.semantic_gateway_prompt import build_messages
from app.agent_core.semantic_gateway_schema import SEMANTIC_DECISION_SCHEMA
from app.llm_gateway.models import LLMRequest

ACT_PROTOCOL = {
    "social_message": ("social", "social", "deterministic"),
    "request_capabilities": ("capabilities", "unknown", "deterministic"),
    "request_support": ("support_intake", "unknown", "deterministic"),
    "provide_case_detail": ("case_update", "troubleshooting", "deterministic"),
    "report_failed_attempt": ("case_update", "troubleshooting", "deterministic"),
    "report_failed_attempt_and_request_next_step": ("technical_follow_up", "troubleshooting", "retrieve"),
    "request_next_step": ("technical_follow_up", "troubleshooting", None),
    "ask_technical_question": ("technical_query", "unknown", "retrieve"),
    "provide_explicit_source": ("explicit_source", "unknown", "retrieve"),
    "request_escalation": ("escalation", "escalation", "escalate"),
    "ambiguous_reference": ("clarification", "unknown", "clarification"),
    "change_topic": ("clarification", "unknown", "clarification"),
    "out_of_scope": ("out_of_scope", "unknown", "legacy_fallback")
}

UPDATE_TYPES = {
    "product", "process", "symptom", "attempted_action", "attempt_result",
    "affected_scope", "error_message", "evidence", "technical_context",
    "resolution_status"
}

def extract_json(text):
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I | re.S).strip()
    try:
        return json.loads(value)
    except Exception:
        match = re.search(r"\{.*\}", value, re.S)
        if not match:
            raise ValueError("model_output_not_json")
        return json.loads(match.group(0))

def normalize(data):
    if not isinstance(data, dict):
        raise ValueError("decision_not_object")
    act = str(data.get("conversation_act") or "")
    if act not in ACT_PROTOCOL:
        raise ValueError(f"unsupported_conversation_act:{act}")
    mode = str(data.get("response_mode") or "")
    if mode not in {"deterministic", "clarification", "retrieve", "escalate", "legacy_fallback"}:
        raise ValueError(f"unsupported_response_mode:{mode}")
    updates = []
    for item in data.get("state_updates") or []:
        if not isinstance(item, dict):
            continue
        typ = str(item.get("type") or "")
        value = str(item.get("value") or "").strip()
        if typ not in UPDATE_TYPES or not value:
            continue
        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0))))
        except Exception:
            confidence = 0.0
        updates.append({"type": typ, "value": value[:400], "confidence": confidence})
    normalized = dict(data)
    normalized["conversation_act"] = act
    normalized["response_mode"] = mode
    normalized["state_updates"] = updates
    return normalized

def derive_protocol(data, state):
    route, intent, fixed_mode = ACT_PROTOCOL[data["conversation_act"]]
    mode = data["response_mode"]
    if fixed_mode is not None:
        mode = fixed_mode
    elif data["conversation_act"] == "request_next_step":
        mode = "retrieve" if state.get("products") and state.get("symptoms") else "clarification"
        route = "technical_follow_up" if mode == "retrieve" else "clarification"
    if data["conversation_act"] == "ask_technical_question":
        question = str((data.get("retrieval_request") or {}).get("question") or "").lower()
        intent = "procedural" if any(word in question for word in ["cómo", "como", "instalar", "configurar", "agregar"]) else "conceptual"
    return {
        "route": route,
        "intent": intent,
        "response_mode": mode,
        "requires_retrieval": mode == "retrieve",
        "requires_clarification": mode == "clarification",
        "requires_escalation": mode == "escalate"
    }

def consistency_warnings(data, derived):
    warnings = []
    if derived["requires_retrieval"] and not data.get("retrieval_request"):
        warnings.append("retrieval_without_request")
    if not derived["requires_retrieval"] and data.get("retrieval_request"):
        warnings.append("unexpected_retrieval_request")
    if data["conversation_act"] in {"report_failed_attempt", "report_failed_attempt_and_request_next_step"}:
        if not any(x.get("type") == "attempt_result" and x.get("value") == "failed" for x in data.get("state_updates", [])):
            warnings.append("failed_attempt_without_state_update")
    if derived["requires_clarification"] and not data.get("clarification_question"):
        warnings.append("clarification_without_question")
    return warnings

def dimension(expected, actual):
    if expected is None:
        return {"evaluated": False, "passed": True, "expected": None, "actual": actual}
    return {"evaluated": True, "passed": expected == actual, "expected": expected, "actual": actual}

def evaluate_case(gateway, case, max_tokens=180):
    started = time.perf_counter()
    result = gateway.complete(LLMRequest(
        build_messages(case["message"], case.get("state") or {}),
        "semantic_orchestrator", max_tokens, 0.0, SEMANTIC_DECISION_SCHEMA
    ))
    record = {"id": case["id"], "category": case["category"], "message": case["message"], "provider_result": result.to_dict(), "passed": False, "dimensions": {}, "mismatches": []}
    if not result.ok:
        return record
    try:
        data = normalize(extract_json(result.text))
        derived = derive_protocol(data, case.get("state") or {})
    except Exception as exc:
        record["mismatches"].append(f"invalid_semantic_json:{type(exc).__name__}:{exc}")
        return record
    record["model_decision"] = data
    record["derived_decision"] = derived
    record["consistency_warnings"] = consistency_warnings(data, derived)
    expected = case.get("expected") or {}
    update_types = [x.get("type") for x in data.get("state_updates", [])]
    dims = {
        "conversation_act": dimension(expected.get("conversation_act"), data.get("conversation_act")),
        "response_mode": dimension(expected.get("response_mode"), derived.get("response_mode")),
        "route": dimension(expected.get("route"), derived.get("route")),
        "intent": dimension(expected.get("intent"), derived.get("intent")),
        "retrieval_decision": dimension(expected.get("requires_retrieval"), derived.get("requires_retrieval")),
        "state_extraction": {"evaluated": expected.get("update_type") is not None, "passed": expected.get("update_type") is None or expected.get("update_type") in update_types, "expected": expected.get("update_type"), "actual": update_types}
    }
    record["dimensions"] = dims
    for key, item in dims.items():
        if item["evaluated"] and not item["passed"]:
            record["mismatches"].append(f"{key} expected={item['expected']} actual={item['actual']}")
    record["protocol_passed"] = all(dims[k]["passed"] for k in ["conversation_act", "response_mode", "route", "intent", "retrieval_decision"])
    record["state_extraction_passed"] = dims["state_extraction"]["passed"]
    record["passed"] = record["protocol_passed"] and record["state_extraction_passed"] and not record["consistency_warnings"]
    record["evaluation_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return record

def summarize(records):
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    dimensions = {}
    categories = {}
    for record in records:
        for key in usage:
            usage[key] += int(record.get("provider_result", {}).get("usage", {}).get(key, 0) or 0)
        category = record.get("category", "unknown")
        categories.setdefault(category, {"total": 0, "passed": 0})
        categories[category]["total"] += 1
        categories[category]["passed"] += int(bool(record.get("passed")))
        for name, item in (record.get("dimensions") or {}).items():
            if not item.get("evaluated"):
                continue
            dimensions.setdefault(name, {"total": 0, "passed": 0})
            dimensions[name]["total"] += 1
            dimensions[name]["passed"] += int(bool(item.get("passed")))
    for item in dimensions.values():
        item["rate"] = round(item["passed"] / max(1, item["total"]), 4)
    return {
        "total": len(records),
        "passed": sum(bool(r.get("passed")) for r in records),
        "failed": sum(not bool(r.get("passed")) for r in records),
        "protocol_passed": sum(bool(r.get("protocol_passed")) for r in records),
        "state_extraction_passed": sum(bool(r.get("state_extraction_passed")) for r in records),
        "usage": usage,
        "dimensions": dimensions,
        "categories": categories,
        "average_latency_ms": round(sum(float(r.get("provider_result", {}).get("latency_ms", 0) or 0) for r in records) / max(1, len(records)), 3)
    }
