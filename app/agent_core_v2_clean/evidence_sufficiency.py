from __future__ import annotations
from dataclasses import dataclass,asdict
from .evidence_authority import canonical_evidence_decision
@dataclass(frozen=True)
class EvidenceAssessment:
 status:str;score:float;reasons:list[str];usable_chunks:int;unique_pages:int;same_document_only:bool;ordered:bool;generation_allowed:bool;internal_knowledge_candidate:bool;coverage_basis:str='selected_evidence';retrieval_quality:float=0.0;relevance_supported:bool=False;canonical_decision:dict|None=None
 def to_dict(self):return asdict(self)
def assess_procedural_evidence(retrieval,intent='procedural'):
 d=canonical_evidence_decision(retrieval,intent); ev=retrieval.get('generation_evidence') or retrieval.get('evidence') or []; exp=retrieval.get('procedural_expansion') or {}; pages={str(x.get('page')) for x in ev if x.get('page') not in (None,'')}; same=bool(exp.get('same_document_only', len({x.get('url') or x.get('source') or x.get('title') for x in ev})<=1)); ordered=bool(exp.get('ordered',True)); score=round((d.object_match+d.operation_match+d.intent_match+d.coverage)/4,3); reasons=[] if d.accepted else [d.reason]
 return EvidenceAssessment(d.status,score,reasons,len(ev),len(pages),same,ordered,d.accepted,d.status not in {'sufficient','partial_but_answerable'},'pages' if pages else 'selected_evidence',float((retrieval.get('selection') or {}).get('quality',0) or 0),d.status!='insufficient',d.to_dict())
def safe_partial_response(a,retrieval):
 return 'Encontré documentación relacionada, pero no cubre suficientemente la operación solicitada.' if a.status=='partial' else 'No encontré evidencia documental aplicable a la operación solicitada.'
