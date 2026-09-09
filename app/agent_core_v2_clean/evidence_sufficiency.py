from __future__ import annotations
from dataclasses import dataclass,asdict
import re
@dataclass(frozen=True)
class EvidenceAssessment:
 status:str;score:float;reasons:list[str];usable_chunks:int;unique_pages:int;same_document_only:bool;ordered:bool;generation_allowed:bool;internal_knowledge_candidate:bool;coverage_basis:str="pages"
 def to_dict(self):return asdict(self)
def _text(e):return " ".join(str(e.get("text") or "").split())
def _page(e):return str(e.get("page") or "").strip()
def _action_density(text):
 verbs=len(re.findall(r"\b(?:abrir|guardar|copiar|pegar|validar|verificar|ejecutar|presionar|seleccionar|configurar|reiniciar|actualizar|confirmar|asignar|sincronizar|autenticar|open|save|copy|validate|verify|run|press|select|configure|restart|update|confirm|assign|sync|authenticate)\w*\b",text.casefold()));structure=len(re.findall(r"(?:^|\n)\s*(?:\d+[.)]|[-*•])\s+",text));return verbs+structure
def assess_procedural_evidence(retrieval):
 exp=retrieval.get("procedural_expansion") or {};evidence=retrieval.get("evidence") or [];usable=[e for e in evidence if len(_text(e))>=80 and _action_density(_text(e))>0];pages={_page(e) for e in usable if _page(e)};same=bool(exp.get("same_document_only"));ordered=bool(exp.get("ordered"));ok=bool(retrieval.get("ok") and exp.get("ok"));web_without_pages=bool(usable) and not pages and all((e.get("url") or e.get("source")) for e in usable);coverage=len(pages) if pages else len(usable) if web_without_pages else 0;basis="chunks_without_pages" if web_without_pages else "pages";reasons=[]
 if not ok:reasons.append("retrieval_or_expansion_failed")
 if not same:reasons.append("multiple_or_unstable_documents")
 if not ordered:reasons.append("unordered_evidence")
 if len(usable)<2:reasons.append("too_few_actionable_chunks")
 if coverage<2:reasons.append("insufficient_evidence_coverage")
 if sum(len(_text(e)) for e in usable)<500:reasons.append("insufficient_actionable_content")
 base=sum((.25 if ok else 0,.2 if same else 0,.15 if ordered else 0,min(.2,len(usable)*.05),min(.2,coverage*.05)));score=round(min(1.,base),3)
 blocking={"retrieval_or_expansion_failed","multiple_or_unstable_documents","unordered_evidence","too_few_actionable_chunks","insufficient_evidence_coverage","insufficient_actionable_content"}
 if not (blocking & set(reasons)) and score>=.75:status="sufficient"
 elif ok and same and usable:status="partial"
 else:status="insufficient"
 return EvidenceAssessment(status,score,reasons,len(usable),len(pages),same,ordered,status=="sufficient",status!="sufficient",basis)
def safe_partial_response(a,retrieval):
 groups=retrieval.get("document_groups") or [];title=(groups[0].get("title") if groups else None) or "la documentación recuperada"
 return f"Encontré evidencia útil en {title}, pero la cobertura no es suficiente para presentar el procedimiento como completo." if a.status=="partial" else "No encontré evidencia documental suficiente y consistente para dar un procedimiento seguro sobre esta solicitud."
