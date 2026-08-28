from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any

ALLOWED_POLICIES={"disabled","hybrid_guarded","general_guidance_only"}
SENSITIVE_INTENTS={"warranty","billing","licensing","security","firmware"}
SENSITIVE_ACTION_MARKERS={"registry","firewall","database","certificate","credential","firmware","delete","remove queue","production change"}

@dataclass
class EvidenceDecision:
    support_level:str
    response_mode:str
    allow_internal_knowledge:bool
    disclosure_required:bool
    escalation_recommended:bool
    restrictions:list[str]
    reason:str
    def to_dict(self)->dict[str,Any]:return asdict(self)

def evaluate_document_support(metrics:dict,policy:str="hybrid_guarded",intent:str="troubleshooting")->EvidenceDecision:
    if policy not in ALLOWED_POLICIES:policy="disabled"
    identity=float(metrics.get("identity_score",0) or 0)
    alignment=float(metrics.get("intent_alignment",0) or 0)
    coverage=float(metrics.get("coverage_score",0) or 0)
    official=bool(metrics.get("official_source",False))
    contradictions=bool(metrics.get("contradictions",False))
    sensitive=bool(metrics.get("sensitive_action",False)) or intent in SENSITIVE_INTENTS
    if contradictions:
        return EvidenceDecision("insufficient","escalate",False,False,True,["conflicting_sources","no_technical_action"],"Retrieved sources conflict.")
    if official and identity>=0.75 and alignment>=0.70 and coverage>=0.65:
        return EvidenceDecision("sufficient","documented",False,False,False,["cite_retrieved_sources"],"Documentation sufficiently supports the response.")
    if identity>=0.60 and alignment>=0.45 and coverage>=0.30:
        if policy=="hybrid_guarded" and not sensitive:
            return EvidenceDecision("partial","hybrid",True,True,False,["separate_documented_and_model_sections","general_reversible_guidance_only","no_sensitive_changes","cite_only_documented_claims"],"Documentation is relevant but incomplete.")
        return EvidenceDecision("partial","documented_limited",False,False,True,["state_documentation_limit","collect_evidence","consider_escalation"],"Documentation is relevant but internal knowledge is restricted.")
    if policy in {"hybrid_guarded","general_guidance_only"} and not sensitive:
        return EvidenceDecision("insufficient","internal_general",True,True,True,["general_guidance_only","observable_or_reversible_steps_only","no_product_specific_procedure","no_sensitive_changes","no_document_citations_for_model_knowledge"],"Documentation does not sufficiently support a technical procedure.")
    return EvidenceDecision("insufficient","escalate",False,False,True,["collect_evidence","no_undocumented_procedure"],"Documentation is insufficient and internal guidance is disabled or restricted.")

def build_response_contract(decision:EvidenceDecision)->dict:
    sections=[]
    if decision.response_mode in {"documented","hybrid","documented_limited"}:
        sections.append({"type":"documented","heading":"Información respaldada por documentación","source_ids_required":True})
    if decision.response_mode in {"hybrid","internal_general"}:
        sections.append({"type":"disclosure","heading":"Cobertura documental","required_text":"La documentación disponible no cubre completamente este escenario. La siguiente orientación complementaria se basa en conocimiento general del modelo y debe validarse antes de aplicarse."})
        sections.append({"type":"model_knowledge","heading":"Orientación general complementaria","source_ids_required":False})
    if decision.escalation_recommended:
        sections.append({"type":"escalation","heading":"Validación o escalamiento","source_ids_required":False})
    return {"support_level":decision.support_level,"response_mode":decision.response_mode,"sections":sections,"restrictions":decision.restrictions,"disclosure_required":decision.disclosure_required}
