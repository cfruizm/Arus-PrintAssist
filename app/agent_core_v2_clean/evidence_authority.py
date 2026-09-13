from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class EvidenceDecision:
    status: str
    generation_mode: str
    reason: str
    selected_ids: list[str]
    product_match: float
    object_match: float
    operation_match: float
    intent_match: float
    coverage: float
    accepted: bool
    def to_dict(self): return asdict(self)

def canonical_evidence_decision(retrieval: dict, intent: str) -> EvidenceDecision:
    sf = retrieval.get('semantic_fit') or {}
    selected = retrieval.get('generation_evidence') or retrieval.get('evidence') or []
    selected_ids = [str(x.get('id')) for x in selected if x.get('id')]
    signals = sf.get('alignment') or {}
    product = float(signals.get('product', sf.get('product_alignment', 0.0)) or 0.0)
    obj = float(signals.get('object', sf.get('object_alignment', 0.0)) or 0.0)
    operation = float(signals.get('operation', sf.get('operation_alignment', 0.0)) or 0.0)
    intent_fit = float(signals.get('intent', sf.get('intent_alignment', 0.0)) or 0.0)
    coverage = float(signals.get('coverage', sf.get('coverage', 0.0)) or 0.0)
    # Backward-compatible fallbacks. A product match alone never authorizes generation.
    if not any((product, obj, operation, intent_fit, coverage)):
        combined = float(sf.get('combined_quality', 0.0) or 0.0)
        quality = float((retrieval.get('selection') or {}).get('quality', 0.0) or 0.0)
        obj = combined
        operation = quality
        intent_fit = combined
        coverage = min(1.0, len(selected_ids) / 3.0)
    required = (obj >= .35 and intent_fit >= .35)
    if intent in {'procedural','requirements','troubleshooting'}:
        required = required and operation >= .30
    strong = required and coverage >= .55 and bool(selected_ids)
    partial = bool(selected_ids) and (required or max(obj, operation, intent_fit) >= .30)
    if strong:
        return EvidenceDecision('sufficient','documented','aligned_and_covered',selected_ids,product,obj,operation,intent_fit,coverage,True)
    if partial:
        return EvidenceDecision('partial','documented_plus_internal','aligned_but_incomplete',selected_ids,product,obj,operation,intent_fit,coverage,False)
    return EvidenceDecision('insufficient','internal_only','product_or_keyword_match_without_operational_fit',selected_ids,product,obj,operation,intent_fit,coverage,False)
