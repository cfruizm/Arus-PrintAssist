from __future__ import annotations
import json
from typing import Any

APPLICABILITY = {"direct", "partial", "conditional", "contextual", "not_applicable"}
MATCH = {"same", "related", "different", "unknown"}
SCOPE = {"same", "narrower", "broader", "conditional", "different", "unknown"}
OBJECT = {"product", "component", "operation", "incident", "feature", "unknown"}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "applicability": {"type": "string", "enum": sorted(APPLICABILITY)},
                    "subject_match": {"type": "string", "enum": sorted(MATCH)},
                    "task_match": {"type": "string", "enum": sorted(MATCH)},
                    "scope_relation": {"type": "string", "enum": sorted(SCOPE)},
                    "requested_object": {"type": "string", "enum": sorted(OBJECT)},
                    "source_object": {"type": "string", "enum": sorted(OBJECT)},
                    "reason": {"type": "string"},
                    "conditions": {"type": "array", "items": {"type": "string"}},
                    "supported_claims": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "id", "applicability", "subject_match", "task_match",
                    "scope_relation", "requested_object", "source_object",
                    "reason", "conditions", "supported_claims"
                ],
            },
        }
    },
    "required": ["assessments"],
}


def _extract_json(text: str) -> dict[str, Any]:
    text = str(text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("evidence_judge_incomplete_json")
    return json.loads(text[start:end + 1])


def _clip(value: Any, size: int) -> str:
    return " ".join(str(value or "").split())[:size]


def _compact_metadata(source: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(source.get("metadata") or {})
    allowed = (
        "product", "component", "document_family", "source_type",
        "language", "section_title", "content_type"
    )
    return {key: metadata.get(key) for key in allowed if metadata.get(key) not in (None, "")}


def _normalized_assessment(item: dict[str, Any], valid_ids: set[str]) -> dict[str, Any] | None:
    source = dict(item or {})
    source_id = str(source.get("id") or "").strip()
    if source_id not in valid_ids:
        return None
    reason = str(source.get("reason") or source.get("reasoning") or "").strip()[:220]
    applicability = str(source.get("applicability") or "not_applicable")
    subject_match = str(source.get("subject_match") or "unknown")
    task_match = str(source.get("task_match") or "unknown")
    scope_relation = str(source.get("scope_relation") or "unknown")
    requested_object = str(source.get("requested_object") or "unknown")
    source_object = str(source.get("source_object") or "unknown")
    if applicability not in APPLICABILITY:
        applicability = "not_applicable"
    if subject_match not in MATCH:
        subject_match = "unknown"
    if task_match not in MATCH:
        task_match = "unknown"
    if scope_relation not in SCOPE:
        scope_relation = "unknown"
    if requested_object not in OBJECT:
        requested_object = "unknown"
    if source_object not in OBJECT:
        source_object = "unknown"
    claims = [_clip(value, 190) for value in (source.get("supported_claims") or []) if _clip(value, 190)][:4]
    conditions = [_clip(value, 130) for value in (source.get("conditions") or []) if _clip(value, 130)][:3]
    model_applicability = applicability

    # Python enforces the scope contract after the semantic judgment.
    if scope_relation in {"narrower", "broader"} and applicability == "direct":
        applicability = "partial"
    if scope_relation == "conditional" and applicability == "direct":
        applicability = "conditional"
    if subject_match == "different" or task_match == "different" or scope_relation == "different":
        applicability = "not_applicable"
    if applicability == "direct" and not claims:
        applicability = "contextual"
    if applicability in {"partial", "conditional"} and not claims:
        applicability = "contextual"

    return {
        "id": source_id,
        "applicability": applicability,
        "model_applicability": model_applicability,
        "subject_match": subject_match,
        "task_match": task_match,
        "scope_relation": scope_relation,
        "requested_object": requested_object,
        "source_object": source_object,
        "reason": reason,
        "conditions": conditions,
        "supported_claims": claims,
        "scope_downgraded": applicability != model_applicability,
    }


class SemanticEvidenceJudge:
    def __init__(self, gateway, max_tokens: int = 300, max_candidates: int = 6):
        self.gateway = gateway
        self.max_tokens = max(240, min(360, int(max_tokens)))
        self.max_candidates = max(1, min(6, int(max_candidates)))

    def evaluate(self, query, intent, entities, candidates):
        from app.llm_gateway.models import LLMRequest
        selected = list(candidates or [])[: self.max_candidates]
        valid_ids = {str(item.get("id") or "") for item in selected}
        payload = {
            "request": query,
            "intent": intent,
            "entities": [
                {
                    "kind": getattr(item, "kind", None) or (item.get("kind") if isinstance(item, dict) else None),
                    "name": getattr(item, "canonical_name", None) or (item.get("canonical_name") if isinstance(item, dict) else None),
                }
                for item in entities
            ],
            "candidates": [
                {
                    "id": item.get("id"),
                    "title": _clip(item.get("title"), 150),
                    "metadata": _compact_metadata(item),
                    "excerpt": _clip(item.get("text"), 520),
                }
                for item in selected
            ],
        }
        system = (
            "Evaluate semantic evidence for the exact request across languages. "
            "Direct requires the same subject, task, requested object and scope. "
            "A component, module or operation is narrower than a product-wide request. "
            "Contextual evidence may support background or diagnostic questions but not a procedure or complete answer. "
            "Every direct, partial or conditional assessment must include at least one supported_claim grounded in the excerpt. "
            "Do not invent facts. Return compact JSON only."
        )
        result = self.gateway.complete(LLMRequest(
            [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
            "agent_core_v2_evidence_judge", self.max_tokens, 0.0, JUDGE_SCHEMA,
        ))
        if not result.ok or result.finish_reason == "length":
            return {"ok": False, "error": "judge_truncated" if result.finish_reason == "length" else (result.error_message or "judge_provider_error"), "assessments": [], "provider_result": result.to_dict()}
        try:
            raw = _extract_json(result.text)
        except Exception as exc:
            return {"ok": False, "error": f"judge_invalid_json:{exc}", "assessments": [], "provider_result": result.to_dict()}
        assessments, seen = [], set()
        for item in raw.get("assessments") or []:
            normalized = _normalized_assessment(item, valid_ids)
            if normalized and normalized["id"] not in seen:
                assessments.append(normalized)
                seen.add(normalized["id"])
        for missing in sorted(valid_ids - seen):
            assessments.append({
                "id": missing, "applicability": "not_applicable", "model_applicability": "not_applicable",
                "subject_match": "unknown", "task_match": "unknown", "scope_relation": "unknown",
                "requested_object": "unknown", "source_object": "unknown", "reason": "No valid assessment returned.",
                "conditions": [], "supported_claims": [], "scope_downgraded": False,
            })
        return {"ok": True, "assessments": assessments, "provider_result": result.to_dict(), "compact_candidate_count": len(selected)}


def merge_judgment(candidates, result):
    mapping = {item["id"]: item for item in (result.get("assessments") or [])}
    merged = []
    for source in candidates or []:
        item = dict(source)
        assessment = mapping.get(str(item.get("id"))) or {
            "id": str(item.get("id")), "applicability": "not_applicable", "model_applicability": "not_applicable",
            "subject_match": "unknown", "task_match": "unknown", "scope_relation": "unknown",
            "requested_object": "unknown", "source_object": "unknown", "reason": "Semantic judge unavailable.",
            "conditions": [], "supported_claims": [], "scope_downgraded": False,
        }
        item["semantic_assessment"] = assessment
        applicability = assessment["applicability"]
        item["eligible"] = applicability != "not_applicable"
        item["citable"] = applicability in {"direct", "partial", "conditional"} and bool(assessment["supported_claims"])
        item["citation_scope"] = "direct" if applicability == "direct" else "qualified" if item["citable"] else "none"
        merged.append(item)
    categories = {name: [item for item in merged if item["semantic_assessment"]["applicability"] == name] for name in APPLICABILITY}
    applicable = [item for item in merged if item["citable"]]
    all_narrower = bool(applicable) and all(item["semantic_assessment"]["scope_relation"] == "narrower" for item in applicable)
    requested_objects = sorted({item["semantic_assessment"]["requested_object"] for item in merged if item["semantic_assessment"]["requested_object"] != "unknown"})
    return {
        "retrieved": merged,
        "direct": categories["direct"], "partial": categories["partial"], "conditional": categories["conditional"],
        "contextual": categories["contextual"], "not_applicable": categories["not_applicable"],
        "citable": applicable,
        "coverage": {
            "has_direct_same_scope": any(item["semantic_assessment"]["scope_relation"] == "same" for item in categories["direct"]),
            "has_narrower_sources": any(item["semantic_assessment"]["scope_relation"] == "narrower" for item in applicable),
            "all_applicable_sources_narrower": all_narrower,
            "requested_objects": requested_objects,
            "coverage_mode": "narrower_only" if all_narrower else "direct" if categories["direct"] else "qualified" if applicable else "contextual_only" if categories["contextual"] else "none",
        },
        "counts": {
            "retrieved": len(merged), "direct": len(categories["direct"]), "partial": len(categories["partial"]),
            "conditional": len(categories["conditional"]), "contextual": len(categories["contextual"]), "citable": len(applicable),
        },
    }
