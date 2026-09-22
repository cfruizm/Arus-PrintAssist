from __future__ import annotations
from dataclasses import dataclass,asdict
from copy import deepcopy
from .entity_scope import normalize_scope
from .citation_registry import register_evidence
from .response_coverage import response_shape
@dataclass(frozen=True)
class ResponsePlan:
 schema_version:int;request:dict;evidence_plan:dict;response_plan:dict
 def to_dict(self):return asdict(self)
def build_response_plan(message,u,retrieval,decision=None):
 u=u or {};details=u.get('goal_updates') or {};scope=normalize_scope(details);intent=str(u.get('intent') or 'unknown');guard=(retrieval or {}).get('procedural_scope_guard') or {};verdict=(retrieval or {}).get('evidence_verdict') or {};evidence=list(verdict.get('selected_evidence') or (retrieval or {}).get('generation_evidence') or (retrieval or {}).get('evidence') or []);decision=decision or {};missing=[]
 if intent=='procedural' and not verdict.get('accepted') and not guard.get('direct_procedure_match_count'):
  if scope.manufacturer and not scope.model:missing.append('model')
  if scope.product and scope.architecture and not scope.operating_system:missing.append('operating_system')
 example=bool(evidence) and bool(guard.get('restricted_to_example')) and not verdict.get('accepted');documented=bool(evidence) and bool(verdict.get('accepted',decision.get('status')!='insufficient'));decision={**decision,'status':verdict.get('status',decision.get('status'))};registered,mapping=register_evidence(evidence if documented else []);mode='documented' if documented and decision.get('status')=='sufficient' else 'hybrid' if documented else 'general_guidance_with_example' if example else 'internal'
 request={'intent':intent,'response_shape':response_shape(intent),'operation':details.get('operation') or u.get('current_goal') or '','subject':details.get('subject') or u.get('current_goal') or '','scope':scope.to_dict(),'missing_material_details':missing,'message':message}
 ep={'status':decision.get('status') or ('partial' if example else 'insufficient'),'mode':mode,'documented_ids':[x['id'] for x in registered],'example_ids':[str(x.get('id')) for x in evidence[:1]] if example else [],'citation_map':mapping,'citation_namespace':'canonical','selected_evidence':registered,'rejected':{'scope_mismatch':[str(x.get('id')) for x in evidence] if example else [],'carried_context':[],'duplicate':[]}}
 rp={'mode':mode,'must_answer_general':not documented,'must_ask_one_detail':bool(missing),'question_target':missing[0] if missing else None,'allow_documented_claims':documented,'allow_internal_guidance':not documented or mode=='hybrid','allow_example_claims':example,'complete_goal':documented and not missing};return ResponsePlan(1,request,ep,rp)
def apply_plan(retrieval,plan):
 out=deepcopy(retrieval or {});out['response_plan']=plan.to_dict();mode=plan.response_plan['mode']
 if mode in {'documented','hybrid'}:out['generation_evidence']=deepcopy(plan.evidence_plan['selected_evidence']);out['evidence']=deepcopy(plan.evidence_plan['selected_evidence'])
 else:out['generation_evidence']=[];out['evidence']=[];out['_answer_context']={}
 return out
