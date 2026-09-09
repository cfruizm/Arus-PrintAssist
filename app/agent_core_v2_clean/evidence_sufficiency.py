from __future__ import annotations
from dataclasses import dataclass,asdict
import re

@dataclass(frozen=True)
class EvidenceAssessment:
    status:str
    score:float
    reasons:list[str]
    usable_chunks:int
    unique_pages:int
    same_document_only:bool
    ordered:bool
    generation_allowed:bool
    internal_knowledge_candidate:bool
    def to_dict(self):return asdict(self)

def _text(e):return " ".join(str(e.get("text") or "").split())
def _page(e):return str(e.get("page") or "").strip()
def _action_density(text):
    # Language-agnostic structural signals, not products, procedures or benchmark phrases.
    verbs=len(re.findall(r"\b(?:abrir|guardar|copiar|pegar|validar|verificar|ejecutar|presionar|seleccionar|configurar|reiniciar|actualizar|confirmar|open|save|copy|validate|verify|run|press|select|configure|restart|update|confirm)\w*\b",text.casefold()))
    structure=len(re.findall(r"(?:^|\n)\s*(?:\d+[.)]|[-*•])\s+",text))
    return verbs+structure

def assess_procedural_evidence(retrieval:dict)->EvidenceAssessment:
    exp=retrieval.get("procedural_expansion") or {};evidence=retrieval.get("evidence") or []
    usable=[e for e in evidence if len(_text(e))>=80 and _action_density(_text(e))>0]
    pages={_page(e) for e in usable if _page(e)};reasons=[]
    same=bool(exp.get("same_document_only"));ordered=bool(exp.get("ordered"));ok=bool(retrieval.get("ok") and exp.get("ok"))
    if not ok:reasons.append("retrieval_or_expansion_failed")
    if not same:reasons.append("multiple_or_unstable_documents")
    if not ordered:reasons.append("unordered_evidence")
    if len(usable)<2:reasons.append("too_few_actionable_chunks")
    if len(pages)<2:reasons.append("insufficient_page_coverage")
    total_chars=sum(len(_text(e)) for e in usable)
    if total_chars<500:reasons.append("insufficient_actionable_content")
    base=sum((0.25 if ok else 0,0.2 if same else 0,0.15 if ordered else 0,min(0.2,len(usable)*0.05),min(0.2,len(pages)*0.05)))
    score=round(min(1.0,base),3)
    if not reasons and score>=0.75:status="sufficient"
    elif ok and same and usable:status="partial"
    else:status="insufficient"
    return EvidenceAssessment(status,score,reasons,len(usable),len(pages),same,ordered,status=="sufficient",status in {"partial","insufficient"})

def safe_partial_response(assessment:EvidenceAssessment,retrieval:dict)->str:
    groups=retrieval.get("document_groups") or [];title=(groups[0].get("title") if groups else None) or "la documentación recuperada"
    if assessment.status=="partial":return f"Encontré evidencia útil en {title}, pero la cobertura no es suficiente para presentar el procedimiento como completo. Puedo orientar solo con la parte documentada o complementar después con conocimiento interno claramente advertido."
    return f"No encontré evidencia documental suficiente y consistente para dar un procedimiento seguro sobre esta solicitud. No presentaré pasos incompletos como si fueran un procedimiento validado."
