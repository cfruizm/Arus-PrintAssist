from __future__ import annotations
import json, re, time
from app.agent_core.semantic_gateway_prompt import build_messages
from app.agent_core.semantic_gateway_schema import SEMANTIC_DECISION_SCHEMA
from app.llm_gateway.models import LLMRequest

ALLOWED_UPDATE_TYPES = {
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

def normalize_decision(data):
    if not isinstance(data, dict):
        raise ValueError("decision_not_object")
    updates = []
    for item in data.get("state_updates") or []:
        if not isinstance(item, dict):
            continue
        update_type = str(item.get("type") or "")
        value = str(item.get("value") or "").strip()
        if update_type not in ALLOWED_UPDATE_TYPES or not value:
            continue
        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0))))
        except Exception:
            confidence = 0.0
        updates.append({"type": update_type, "value": value[:400], "confidence": confidence})
    result = dict(data)
    result["state_updates"] = updates
    return result

def consistency_warnings(data):
    warnings = []
    mode = data.get("response_mode")
    if mode == "retrieve" and not data.get("requires_retrieval"):
        warnings.append("retrieve_mode_without_flag")
    if data.get("requires_retrieval") and not data.get("retrieval_request"):
        warnings.append("retrieval_without_request")
    if mode == "clarification" and not data.get("requires_clarification"):
        warnings.append("clarification_mode_without_flag")
    if mode == "escalate" and not data.get("requires_escalation"):
        warnings.append("escalation_mode_without_flag")
    if data.get("route") == "case_update" and any(x.get("type") == "affected_scope" for x in data.get("state_updates", [])) and data.get("intent") != "troubleshooting":
        warnings.append("impact_update_wrong_intent")
    return warnings

def dimension(name, expected, actual):
    if expected is None:
        return {"evaluated": False, "passed": True, "expected": None, "actual": actual}
    return {"evaluated": True, "passed": expected == actual, "expected": expected, "actual": actual}

def evaluate_case(gateway, case, max_tokens=220):
    started = time.perf_counter()
    result = gateway.complete(LLMRequest(
        build_messages(case["message"], case.get("state") or {}),
        "semantic_orchestrator", max_tokens, 0.0, SEMANTIC_DECISION_SCHEMA
    ))
    record = {
        "id": case["id"], "category": case["category"],
        "message": case["message"], "provider_result": result.to_dict(),
        "passed": False, "dimensions": {}, "mismatches": []
    }
    if not result.ok:
        return record
    try:
        data = normalize_decision(extract_json(result.text))
    except Exception as exc:
        record["mismatches"].append(f"invalid_semantic_json:{type(exc).__name__}")
        return record
    record["decision"] = data
    record["consistency_warnings"] = consistency_warnings(data)
    expected = case.get("expected") or {}
    update_types = [item.get("type") for item in data.get("state_updates", [])]
    dims = {
        "route": dimension("route", expected.get("route"), data.get("route")),
        "intent": dimension("intent", expected.get("intent"), data.get("intent")),
        "response_mode": dimension("response_mode", expected.get("response_mode"), data.get("response_mode")),
        "retrieval_decision": dimension("retrieval_decision", expected.get("requires_retrieval"), data.get("requires_retrieval")),
        "clarification_decision": dimension("clarification_decision", expected.get("requires_clarification"), data.get("requires_clarification")),
        "escalation_decision": dimension("escalation_decision", expected.get("requires_escalation"), data.get("requires_escalation")),
        "state_extraction": {
            "evaluated": expected.get("update_type") is not None,
            "passed": expected.get("update_type") is None or expected.get("update_type") in update_types,
            "expected": expected.get("update_type"), "actual": update_types
        }
    }
    record["dimensions"] = dims
    for key, item in dims.items():
        if item["evaluated"] and not item["passed"]:
            record["mismatches"].append(f"{key} expected={item['expected']} actual={item['actual']}")
    record["operational_passed"] = all(dims[k]["passed"] for k in ["route", "intent", "response_mode", "retrieval_decision", "clarification_decision", "escalation_decision"])
    record["state_extraction_passed"] = dims["state_extraction"]["passed"]
    record["passed"] = record["operational_passed"] and record["state_extraction_passed"] and not record["consistency_warnings"]
    record["evaluation_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return record

def summarize(records):
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    dimension_totals = {}
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
            dimension_totals.setdefault(name, {"total": 0, "passed": 0})
            dimension_totals[name]["total"] += 1
            dimension_totals[name]["passed"] += int(bool(item.get("passed")))
    for item in dimension_totals.values():
        item["rate"] = round(item["passed"] / max(1, item["total"]), 4)
    return {
        "total": len(records),
        "passed": sum(bool(r.get("passed")) for r in records),
        "failed": sum(not bool(r.get("passed")) for r in records),
        "operational_passed": sum(bool(r.get("operational_passed")) for r in records),
        "state_extraction_passed": sum(bool(r.get("state_extraction_passed")) for r in records),
        "usage": usage, "dimensions": dimension_totals, "categories": categories,
        "average_latency_ms": round(sum(float(r.get("provider_result", {}).get("latency_ms", 0) or 0) for r in records) / max(1, len(records)), 3)
    }
