from __future__ import annotations
from dataclasses import dataclass
from typing import Callable,Sequence
@dataclass(frozen=True)
class CoverageAudit:
 required:tuple[str,...];represented:tuple[str,...];missing:tuple[str,...];complete:bool
def audit_enumerated_coverage(required_options:Sequence[str],answer:str,entails:Callable[[str,str],bool]|None=None):
 required=tuple(dict.fromkeys(str(x).strip() for x in required_options if str(x).strip()));low=str(answer or "").casefold();represented=[]
 for option in required:
  present=option.casefold() in low or bool(entails and entails(option,answer))
  if present:represented.append(option)
 missing=tuple(x for x in required if x not in represented)
 return CoverageAudit(required,tuple(represented),missing,not missing)
def response_shape(intent):
 return {"requirements":{"primary_claims":["prerequisite","compatibility_condition","required_input","dependency"],"reject_primary":["installation_step","product_specific_configuration"]},"enumeration":{"cover_all_documented_options":True},"comparison":{"compare_all_requested_subjects":True},"procedural":{"ordered_steps":True},"focused_step":{"repeat_full_procedure":False},"troubleshooting":{"respect_confirmed_attempts":True}}.get(str(intent or "").casefold(),{"proportional":True})
