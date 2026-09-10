from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any

@dataclass
class FactRecord:
 key:str
 value:str
 origin:str="user"
 status:str="confirmed"
 turn:int=0
 def to_dict(self):return asdict(self)

@dataclass
class RequestScope:
 subject:str=""
 operation:str=""
 breadth:str="unknown"
 qualifiers:list[str]=field(default_factory=list)
 def to_dict(self):return asdict(self)

def facts_from_memory(memory):
 records=getattr(memory,"fact_records",{}) or {}
 return [dict(v) for v in records.values() if isinstance(v,dict)]

def build_response_contract(memory,understanding,retrieval=None):
 confirmed=[x for x in facts_from_memory(memory) if x.get("status")=="confirmed"]
 missing=[]
 target=getattr(understanding,"clarification_target",None)
 if target and target not in {x.get("key") for x in confirmed}:missing.append(target)
 scope=getattr(understanding,"request_scope",None) or {}
 return {"confirmed_facts":confirmed,"unresolved_facts":missing,"request_scope":scope,"evidence_scope":(retrieval or {}).get("evidence_scope") or {}}

def validate_response_contract(text,contract):
 value=" ".join(str(text or "").split()).casefold();issues=[]
 for fact in contract.get("confirmed_facts") or []:
  v=str(fact.get("value") or "").strip().casefold()
  if not v:continue
  denial=("no se ha confirmado","sin confirmar","falta confirmar","not confirmed","has not been confirmed")
  if any(x in value for x in denial):issues.append({"type":"possible_confirmed_fact_contradiction","key":fact.get("key"),"value":fact.get("value")})
 return {"valid":not issues,"issues":issues,"confirmed_fact_count":len(contract.get("confirmed_facts") or []),"unresolved_fact_count":len(contract.get("unresolved_facts") or [])}
