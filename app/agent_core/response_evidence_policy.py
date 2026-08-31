from __future__ import annotations
from dataclasses import dataclass,asdict

@dataclass
class EvidenceDecision:
    support_level:str
    response_mode:str
    allow_internal_knowledge:bool
    disclosure_required:bool
    escalation_recommended:bool
    restrictions:list[str]
    reason:str
    def to_dict(self):return asdict(self)

def _num(metrics,key):
    try:return max(0.0,min(1.0,float(metrics.get(key,0.0))))
    except Exception:return 0.0

def evaluate_document_support(metrics:dict,policy:str,intent:str)->EvidenceDecision:
    identity=_num(metrics,"identity_score");alignment=_num(metrics,"intent_alignment");coverage=_num(metrics,"coverage_score")
    contradictions=bool(metrics.get("contradictions"));sensitive=bool(metrics.get("sensitive"));intent=str(intent or "unknown");policy=str(policy or "disabled")
    if contradictions:return EvidenceDecision("conflicting","escalate",False,True,True,["no_unverified_procedure","collect_evidence_only"],"Retrieved sources conflict.")
    if sensitive and coverage<0.75:return EvidenceDecision("insufficient","escalate",False,True,True,["no_sensitive_changes","collect_evidence_only"],"Sensitive action lacks sufficient documentation.")
    sufficient=identity>=0.75 and alignment>=0.60 and coverage>=0.60
    partial=identity>=0.65 and alignment>=0.30 and coverage>=0.30
    if sufficient:return EvidenceDecision("sufficient","documented",False,False,False,["documented_claims_only","real_source_ids_only"],"Documentation sufficiently supports the answer.")
    # Troubleshooting cannot become a free technical procedure when evidence is weak.
    if intent=="troubleshooting" and not partial:
        return EvidenceDecision("insufficient","escalate",False,True,True,["collect_evidence_only","no_product_specific_procedure","no_configuration_changes","no_service_restart","no_network_commands","no_unverified_logs"],"Troubleshooting lacks sufficient documentary support.")
    if partial:
        allow=policy=="hybrid_guarded"
        return EvidenceDecision("partial","hybrid" if allow else "escalate",allow,True,True,["general_guidance_only","observable_or_reversible_steps_only","no_sensitive_changes","no_document_citations_for_model_knowledge"],"Documentation partially supports the answer.")
    if intent in {"conceptual","architecture"} and policy=="hybrid_guarded":
        return EvidenceDecision("insufficient","internal_general",True,True,True,["conceptual_explanation_only","no_product_specific_procedure","no_sensitive_changes","no_document_citations_for_model_knowledge"],"Conceptual guidance may be provided with disclosure.")
    return EvidenceDecision("insufficient","escalate",False,True,True,["collect_evidence_only","no_product_specific_procedure","no_sensitive_changes"],"Documentation does not sufficiently support a technical answer.")

def build_response_contract(decision:EvidenceDecision)->dict:
    disclosure="La documentación disponible no cubre completamente este escenario. La orientación no documentada, si está permitida, debe validarse antes de aplicarse."
    if decision.response_mode=="documented":sections=[{"type":"documented","heading":"Información respaldada por documentación","source_ids_required":True},{"type":"sources","heading":"Fuentes","source_ids_required":True}]
    elif decision.response_mode=="hybrid":sections=[{"type":"documented","heading":"Información respaldada por documentación","source_ids_required":True},{"type":"disclosure","heading":"Cobertura documental","required_text":disclosure},{"type":"model_knowledge","heading":"Orientación general complementaria","source_ids_required":False},{"type":"escalation","heading":"Validación o escalamiento","source_ids_required":False}]
    elif decision.response_mode=="internal_general":sections=[{"type":"disclosure","heading":"Cobertura documental","required_text":disclosure},{"type":"model_knowledge","heading":"Orientación general complementaria","source_ids_required":False},{"type":"escalation","heading":"Validación o escalamiento","source_ids_required":False}]
    else:sections=[{"type":"disclosure","heading":"Cobertura documental","required_text":"La documentación recuperada no permite indicar un procedimiento técnico confiable para este escenario."},{"type":"evidence","heading":"Evidencia por recopilar","source_ids_required":False},{"type":"escalation","heading":"Escalamiento recomendado","source_ids_required":False}]
    return {"support_level":decision.support_level,"response_mode":decision.response_mode,"sections":sections,"restrictions":decision.restrictions,"disclosure_required":decision.disclosure_required}
