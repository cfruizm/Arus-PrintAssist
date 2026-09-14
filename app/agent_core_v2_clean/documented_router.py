from __future__ import annotations
from copy import deepcopy
from .procedural_answer import ProceduralAnswerComposer,fingerprint as procedural_fingerprint,PROMPT_VERSION as PROCEDURAL_PROMPT_VERSION
from .evidence_sufficiency import assess_procedural_evidence
from .internal_knowledge import ControlledInternalKnowledgeComposer,fingerprint as internal_fingerprint,PROMPT_VERSION as INTERNAL_PROMPT_VERSION
from .topic_boundary import infer_topic_boundary,sanitize_new_topic_state
from .procedural_recovery import compact_documented_instruction,should_compact_retry
from .evidence_boundary import enforce_evidence_boundary,normalize_citation_groups,scoped_generation_instruction
from .conceptual_route import prepare_conceptual_retrieval,conceptual_assessment
from .procedural_scope import constrain_generic_procedure,scoped_assessment_override

def _valid_cached(item):
 a=(item or {}).get('answer') or {};return a.get('mode') in {'procedural_documented_answer','controlled_internal_knowledge','controlled_internal_knowledge_partial'}
def _get_cache(store,name,key):
 item=store.setdefault(name,{}).get(key)
 if item and not _valid_cached(item):store[name].pop(key,None);return None
 return item
def _knowledge_flags(validation,valid):
 documented=bool((validation or {}).get('documented_citations'));return {'documented_evidence_used':documented,'internal_knowledge_used':valid,'knowledge_mode':'documented_plus_internal' if documented and valid else 'internal_only' if valid else 'none'}
def _prepare_boundary(result,store):
 before=result.get('state_before') or {};u=result.get('understanding') or {};boundary=infer_topic_boundary(before,u);result['topic_boundary']=boundary.to_dict()
 if boundary.relation=='new_topic':u['user_act']='new_request';u['topic_relation']='new_topic';sanitize_new_topic_state(store['memory'],u,before);result['understanding']=u;result['state_after']=deepcopy(store['memory'].to_dict())
 result['retrieval']=enforce_evidence_boundary(result.get('retrieval') or {},boundary.relation);return result
def _internal(result,message,gateway,budget,store,model,assessment):
 u=result.get('understanding') or {};r=result.get('retrieval') or {};key=internal_fingerprint(message,u,r,assessment,model);cache='internal_knowledge_cache';cached=_get_cache(store,cache,key)
 if cached:result['answer']=deepcopy(cached['answer']);result['internal_knowledge']={**deepcopy(cached['diagnostic']),'cache_hit':True};return result,{'skipped':True,'reason':'internal_knowledge_cache'}
 allowed,reason=budget.can_call(store['telemetry'],estimated_tokens=1800)
 if not allowed:return result,{'skipped':True,'reason':'internal_knowledge_budget_block','block_reason':reason}
 c=ControlledInternalKnowledgeComposer(gateway,520);a=c.compose(message,u,r,assessment);valid=a.mode in {'controlled_internal_knowledge','controlled_internal_knowledge_partial'};payload=a.to_dict();payload['text']=normalize_citation_groups(payload.get('text',''));payload.update(_knowledge_flags(c.validation,valid));result['answer']=payload;diag={'enabled':True,'cache_hit':False,'prompt_version':INTERNAL_PROMPT_VERSION,'trigger_status':assessment.get('status'),'trigger_reasons':assessment.get('reasons'),'validation':deepcopy(c.validation)};result['internal_knowledge']=diag
 if valid:store['memory'].pending_goal.status='partially_answered' if a.mode.endswith('_partial') else 'needs_verification';result['state_after']=deepcopy(store['memory'].to_dict());store.setdefault(cache,{})[key]={'answer':deepcopy(payload),'diagnostic':deepcopy(diag)}
 return result,c.last_provider_result
def maybe_generate_procedural(result,message,gateway,budget,store,model=''):
 result=_prepare_boundary(result,store)
 if (result.get('decision') or {}).get('action') not in {'defer_to_retrieval','diagnose_with_retrieval'}:return result,{'skipped':True,'reason':'decision_does_not_authorize_retrieval'}
 u=result.get('understanding') or {};intent=u.get('intent');r=result.get('retrieval') or {}
 if intent=='conceptual':
  boundary=result.get('topic_boundary') or {'relation':u.get('topic_relation'),'changed_dimensions':[]};r=prepare_conceptual_retrieval(r,boundary,u);result['retrieval']=r;assessment=conceptual_assessment(r);result['evidence_sufficiency']=assessment;result['evidence_decision']=assessment['canonical_decision'];result.pop('documented_answer',None);return _internal(result,message,gateway,budget,store,model,assessment)
 if intent not in {'procedural','requirements','troubleshooting'}:return result,None
 if intent=='procedural':r=constrain_generic_procedure(message,u,r);result['retrieval']=r
 assessment=assess_procedural_evidence(r,intent).to_dict();assessment=scoped_assessment_override(r,assessment);result['evidence_sufficiency']=assessment;result['evidence_decision']=assessment.get('canonical_decision')
 if assessment['status']!='sufficient':return _internal(result,message,gateway,budget,store,model,assessment)
 key=procedural_fingerprint(message,u,r,model);cache='procedural_answer_cache';cached=_get_cache(store,cache,key)
 if cached:result['answer']=deepcopy(cached['answer']);result['procedural_answer']={**deepcopy(cached['diagnostic']),'cache_hit':True};return result,{'skipped':True,'reason':'procedural_answer_cache'}
 allowed,reason=budget.can_call(store['telemetry'],estimated_tokens=2700)
 if not allowed:return result,{'skipped':True,'reason':'procedural_budget_block','block_reason':reason}
 c=ProceduralAnswerComposer(gateway,900);note=scoped_generation_instruction(result.get('topic_boundary') or {});a=c.compose(message+('\n\n'+note if note else ''),u,r);attempts=[c.last_provider_result]
 if should_compact_retry(c.last_provider_result):result['procedural_recovery']={'attempted':True,'mode':'compact_documented','knowledge_mode':'documented_only'};compact_r=deepcopy(r);compact_r['generation_evidence']=(r.get('generation_evidence') or [])[:4];compact_r['evidence']=compact_r['generation_evidence'];a=c.compose(message+'\n\n'+compact_documented_instruction(),u,compact_r);attempts.append(c.last_provider_result)
 valid=a.mode=='procedural_documented_answer' and not should_compact_retry(c.last_provider_result);payload=a.to_dict();payload['text']=normalize_citation_groups(payload.get('text',''));payload.update({'documented_evidence_used':valid,'internal_knowledge_used':False,'knowledge_mode':'documented_only' if valid else 'none'});result['answer']=payload;result['procedural_answer']={'enabled':True,'cache_hit':False,'prompt_version':PROCEDURAL_PROMPT_VERSION,'assessment':assessment,'validation':deepcopy(c.validation),'finish_reason':payload.get('finish_reason'),'retry_used':len(attempts)>1,'retry_mode':'compact_documented' if len(attempts)>1 else None}
 if valid:store['memory'].pending_goal.status='complete';result['state_after']=deepcopy(store['memory'].to_dict());store.setdefault(cache,{})[key]={'answer':deepcopy(payload),'diagnostic':deepcopy(result['procedural_answer'])};return result,attempts if len(attempts)>1 else attempts[0]
 recovery={**assessment,'status':'partial','generation_allowed':False,'internal_knowledge_candidate':True,'reasons':[*(assessment.get('reasons') or []),'documented_answer_validation_failed']};return _internal(result,message,gateway,budget,store,model,recovery)
