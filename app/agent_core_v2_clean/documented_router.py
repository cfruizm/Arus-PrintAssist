from __future__ import annotations
from copy import deepcopy
from .procedural_answer import ProceduralAnswerComposer,fingerprint as procedural_fingerprint,PROMPT_VERSION as PROCEDURAL_PROMPT_VERSION
from .evidence_sufficiency import assess_procedural_evidence
from .internal_knowledge import ControlledInternalKnowledgeComposer,fingerprint as internal_fingerprint,PROMPT_VERSION as INTERNAL_PROMPT_VERSION
from .topic_boundary import infer_topic_boundary,sanitize_new_topic_state
from .procedural_recovery import compact_documented_instruction,should_compact_retry,compact_retrieval_for_retry
from .evidence_boundary import enforce_evidence_boundary,normalize_citation_groups
from .conceptual_route import prepare_conceptual_retrieval,conceptual_assessment
from .procedural_scope import constrain_generic_procedure,scoped_assessment_override
from .response_plan_router import plan_turn,assessment_from_plan
from .citation_finalizer import enforce_answer_contract
from .state_scope import enrich_understanding

def _valid_cached(item):
 a=(item or {}).get('answer') or {};return a.get('mode') in {'procedural_documented_answer','controlled_internal_knowledge','controlled_internal_knowledge_partial'}
def _get_cache(store,name,key):
 item=store.setdefault(name,{}).get(key)
 if item and not _valid_cached(item):store[name].pop(key,None);return None
 return item
def _flags(validation,valid):
 documented=bool((validation or {}).get('documented_citations'));return {'documented_evidence_used':documented,'internal_knowledge_used':valid,'knowledge_mode':'documented_plus_internal' if documented and valid else 'internal_only' if valid else 'none'}
def _boundary(result,store):
 before=result.get('state_before') or {};u=result.get('understanding') or {};b=infer_topic_boundary(before,u);result['topic_boundary']=b.to_dict()
 if b.relation=='new_topic':u['user_act']='new_request';u['topic_relation']='new_topic';sanitize_new_topic_state(store['memory'],u,before);result['understanding']=u;result['state_after']=deepcopy(store['memory'].to_dict())
 result['retrieval']=enforce_evidence_boundary(result.get('retrieval') or {},b.relation);return result
def _internal(result,message,gateway,budget,store,model,assessment):
 u=result.get('understanding') or {};r=result.get('retrieval') or {};key=internal_fingerprint(message,u,r,assessment,model);cached=_get_cache(store,'internal_knowledge_cache',key)
 if cached:result['answer']=deepcopy(cached['answer']);result['internal_knowledge']={**deepcopy(cached['diagnostic']),'cache_hit':True};return result,{'skipped':True,'reason':'internal_knowledge_cache'}
 allowed,reason=budget.can_call(store['telemetry'],estimated_tokens=1800)
 if not allowed:return result,{'skipped':True,'reason':'internal_knowledge_budget_block','block_reason':reason}
 c=ControlledInternalKnowledgeComposer(gateway,520);a=c.compose(message,u,r,assessment);valid=a.mode in {'controlled_internal_knowledge','controlled_internal_knowledge_partial'};payload=a.to_dict();payload['text']=normalize_citation_groups(payload.get('text',''));payload.update(_flags(c.validation,valid));payload,audit=enforce_answer_contract(payload,result.get('canonical_response_plan'));result['answer']=payload;diag={'enabled':True,'cache_hit':False,'prompt_version':INTERNAL_PROMPT_VERSION,'trigger_status':assessment.get('status'),'trigger_reasons':assessment.get('reasons'),'validation':deepcopy(c.validation),'canonical_plan_used':True,'citation_audit':audit};result['internal_knowledge']=diag
 if valid:store['memory'].pending_goal.status='partially_answered' if a.mode.endswith('_partial') else 'needs_verification';result['state_after']=deepcopy(store['memory'].to_dict());store.setdefault('internal_knowledge_cache',{})[key]={'answer':deepcopy(payload),'diagnostic':deepcopy(diag)}
 return result,c.last_provider_result
def maybe_generate_procedural(result,message,gateway,budget,store,model=''):
 result=_boundary(result,store);result=enrich_understanding(result)
 if (result.get('decision') or {}).get('action') not in {'defer_to_retrieval','diagnose_with_retrieval'}:return result,{'skipped':True,'reason':'decision_does_not_authorize_retrieval'}
 u=result.get('understanding') or {};intent=u.get('intent');r=result.get('retrieval') or {}
 if intent=='conceptual':b=result.get('topic_boundary') or {'relation':u.get('topic_relation'),'changed_dimensions':[]};r=prepare_conceptual_retrieval(r,b,u);result['retrieval']=r;base=conceptual_assessment(r);result['evidence_decision']=base['canonical_decision']
 elif intent in {'procedural','requirements','troubleshooting'}:
  if intent=='procedural':r=constrain_generic_procedure(message,u,r);result['retrieval']=r
  base=assess_procedural_evidence(r,intent).to_dict();base=scoped_assessment_override(r,base);result['evidence_decision']=base.get('canonical_decision')
 else:return result,None
 result,plan=plan_turn(result,message);assessment=assessment_from_plan(plan,base);result['evidence_sufficiency']=assessment;mode=plan.response_plan['mode']
 if mode!='documented':return _internal(result,message,gateway,budget,store,model,assessment)
 r=result.get('retrieval') or {};key=procedural_fingerprint(message,u,r,model);cached=_get_cache(store,'procedural_answer_cache',key)
 if cached:result['answer']=deepcopy(cached['answer']);result['procedural_answer']={**deepcopy(cached['diagnostic']),'cache_hit':True};return result,{'skipped':True,'reason':'procedural_answer_cache'}
 allowed,reason=budget.can_call(store['telemetry'],estimated_tokens=2700)
 if not allowed:return result,{'skipped':True,'reason':'procedural_budget_block','block_reason':reason}
 c=ProceduralAnswerComposer(gateway,900);a=c.compose(message,u,r);attempts=[c.last_provider_result]
 if should_compact_retry(c.last_provider_result):compact=compact_retrieval_for_retry(r);a=c.compose(message+'\n\n'+compact_documented_instruction(),u,compact);attempts.append(c.last_provider_result);result['procedural_recovery']={'attempted':True,'mode':'ordered_full_stage_compaction','selection':compact.get('procedural_recovery_selection')}
 valid=a.mode=='procedural_documented_answer' and not should_compact_retry(c.last_provider_result);payload=a.to_dict();payload['text']=normalize_citation_groups(payload.get('text',''));payload.update({'documented_evidence_used':valid,'internal_knowledge_used':False,'knowledge_mode':'documented_only' if valid else 'none'});payload,audit=enforce_answer_contract(payload,result.get('canonical_response_plan'));result['answer']=payload;diag={'enabled':True,'cache_hit':False,'prompt_version':PROCEDURAL_PROMPT_VERSION,'assessment':assessment,'validation':deepcopy(c.validation),'retry_used':len(attempts)>1,'citation_audit':audit};result['procedural_answer']=diag
 if valid:store['memory'].pending_goal.status='complete';result['state_after']=deepcopy(store['memory'].to_dict());store.setdefault('procedural_answer_cache',{})[key]={'answer':deepcopy(payload),'diagnostic':deepcopy(diag)};return result,attempts if len(attempts)>1 else attempts[0]
 return _internal(result,message,gateway,budget,store,model,assessment)
