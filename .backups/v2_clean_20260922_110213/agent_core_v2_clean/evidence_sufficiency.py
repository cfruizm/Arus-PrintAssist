from dataclasses import dataclass
@dataclass
class EvidenceAssessment:
    status:str;generation_allowed:bool;internal_knowledge_candidate:bool;reasons:list[str]
def assess_procedural_evidence(r):
    evidence=r.get("evidence") or [];exp=r.get("procedural_expansion") or {}
    if not r.get("ok") or not evidence:return EvidenceAssessment("insufficient",False,False,["retrieval_or_expansion_failed"])
    enough=len(evidence)>=2 and bool(exp.get("same_document_only",True))
    return EvidenceAssessment("sufficient" if enough else "partial",enough,not enough,[])
def safe_partial_response(a,ctx):return "No encontré evidencia documental suficiente para indicar un procedimiento completo sin inventar pasos."
