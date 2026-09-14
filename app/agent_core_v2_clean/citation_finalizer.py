from __future__ import annotations
from dataclasses import dataclass, asdict
import re
_CITE=re.compile(r"\[(R\d+)\]");_SOURCE_LINE=re.compile(r"(?m)^\s*-\s*\[(R\d+)\].*$")
@dataclass(frozen=True)
class CitationAudit:
 cited_ids:list[str];valid_ids:list[str];remapped_ids:dict[str,str];preserved_canonical_ids:list[str];unknown_ids:list[str];stripped_ids:list[str];valid:bool;namespace:str
 def to_dict(self):return asdict(self)
def finalize_citations(text,plan):
 plan=plan or {};ep=plan.get('evidence_plan') or {};rp=plan.get('response_plan') or {};mapping={str(k):str(v) for k,v in (ep.get('citation_map') or {}).items()};valid={str(x) for x in ep.get('documented_ids') or []};namespace=str(ep.get('citation_namespace') or 'canonical');source=str(text or '');remapped={};preserved=[]
 def resolve(cid):
  if cid in valid:preserved.append(cid);return cid
  target=mapping.get(cid)
  if target in valid:remapped[cid]=target;return target
  return cid
 source=_CITE.sub(lambda m:f"[{resolve(m.group(1))}]",source);cited=sorted(set(_CITE.findall(source)));unknown=sorted(x for x in cited if x not in valid);stripped=[]
 if not bool(rp.get('allow_documented_claims')):
  stripped=cited;source=_CITE.sub('',source);source=_SOURCE_LINE.sub('',source);source=re.sub(r"(?m)^\s*\*\*Fuentes documentales\*\*\s*$",'',source);source=re.sub(r"\n{3,}",'\n\n',source).strip();unknown=[]
 audit=CitationAudit(cited,sorted(valid),remapped,sorted(set(preserved)),unknown,stripped,not unknown,namespace);return source,audit
def enforce_answer_contract(payload,canonical_plan):
 result=dict(payload or {});text,audit=finalize_citations(result.get('text',''),canonical_plan);result['text']=text;allow=bool(((canonical_plan or {}).get('response_plan') or {}).get('allow_documented_claims'));internal=bool(result.get('internal_knowledge_used'));result['documented_evidence_used']=allow and bool(audit.cited_ids) and audit.valid
 if internal:result['knowledge_mode']='documented_plus_internal' if result['documented_evidence_used'] else 'internal_only'
 elif result['documented_evidence_used']:result['knowledge_mode']='documented_only'
 return result,audit.to_dict()
