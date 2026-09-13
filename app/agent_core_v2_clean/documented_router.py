from __future__ import annotations
from copy import deepcopy
from .procedural_answer import ProceduralAnswerComposer,fingerprint as procedural_fingerprint,PROMPT_VERSION as PROCEDURAL_PROMPT_VERSION
from .evidence_sufficiency import assess_procedural_evidence
from .internal_knowledge import ControlledInternalKnowledgeComposer,fingerprint as internal_fingerprint,PROMPT_VERSION as INTERNAL_PROMPT_VERSION

def _valid_cached(item):
 a=(item or {}).get('answer') or {};return a.get('mode') in {'procedural_documented_answer','controlled_internal_knowledge','controlled_internal_knowledge_partial'}
def _get_cache(store,name,key):
 item=store.setdefault(name,{}).get(key)
 if item and not _valid_cached(item):store[name].pop(key,None);return None
 return item
def _knowledge_flags(validation,valid):
 documented=bool((validation or {}).get('documented_citations'))
 return {'documented_evidence_used':documented,'internal_knowledge_used':valid,'knowledge_mode':'documented_plus_internal' if documented and valid else 'internal_only' if valid else 'none'}
def _internal(result,message,gateway,budget,store,model,assessment):
 u=result.get('understanding') or {};r=result.get('retrieval') or {};key=internal_fingerprint(message,u,r,assessment,model);cache='internal_knowledge_cache';store.setdefault(cache,{});store.setdefault('cache_metrics',{}).setdefault('internal_knowledge_hits',0);cached=_get_cache(store,cache,key)
 if cached:
  result['answer']=deepcopy(cached['answer']);result['internal_knowledge']={**deepcopy(cached['diagnostic']),'cache_hit':True};store['cache_metrics']['internal_knowledge_hits']+=1;return result,{'skipped':True,'reason':'internal_knowledge_cache'}
 allowed,reason=budget.can_call(store['telemetry'],estimated_tokens=1800)
 if not allowed:return result,{'skipped':True,'reason':'internal_knowledge_budget_block','block_reason':reason}
 c=ControlledInternalKnowledgeComposer(gateway,520);a=c.compose(message,u,r,assessment);valid=a.mode in {'controlled_internal_knowledge','controlled_internal_knowledge_partial'};payload=a.to_dict();payload.update(_knowledge_flags(c.validation,valid));result['answer']=payload;diag={'enabled':True,'cache_hit':False,'prompt_version':INTERNAL_PROMPT_VERSION,'trigger_status':assessment.get('status'),'trigger_reasons':assessment.get('reasons'),'validation':deepcopy(c.validation)};result['internal_knowledge']=diag
 if valid:
  store['memory'].pending_goal.status='partially_answered' if a.mode.endswith('_partial') else 'needs_verification';result['state_after']=deepcopy(store['memory'].to_dict());store[cache][key]={'answer':deepcopy(payload),'diagnostic':deepcopy(diag)}
 return result,c.last_provider_result
def maybe_generate_procedural(result,message,gateway,budget,store,model=''):
 if (result.get('decision') or {}).get('action') not in {'defer_to_retrieval','diagnose_with_retrieval'}:return result,{'skipped':True,'reason':'decision_does_not_authorize_retrieval'}
 u=result.get('understanding') or {};intent=u.get('intent')
 if intent not in {'procedural','requirements','troubleshooting'}:return result,None
 assessment=assess_procedural_evidence(result.get('retrieval') or {},intent).to_dict();result['evidence_sufficiency']=assessment;result['evidence_decision']=assessment.get('canonical_decision')
 if assessment['status']!='sufficient':return _internal(result,message,gateway,budget,store,model,assessment)
 r=result.get('retrieval') or {};key=procedural_fingerprint(message,u,r,model);cache='procedural_answer_cache';cached=_get_cache(store,cache,key)
 if cached:
  result['answer']=deepcopy(cached['answer']);result['procedural_answer']={**deepcopy(cached['diagnostic']),'cache_hit':True};return result,{'skipped':True,'reason':'procedural_answer_cache'}
 allowed,reason=budget.can_call(store['telemetry'],estimated_tokens=2700)
 if not allowed:return result,{'skipped':True,'reason':'procedural_budget_block','block_reason':reason}
 c=ProceduralAnswerComposer(gateway,900);a=c.compose(message,u,r);valid=a.mode=='procedural_documented_answer';payload=a.to_dict();payload.update({'documented_evidence_used':valid,'internal_knowledge_used':False,'knowledge_mode':'documented_only' if valid else 'none'});result['answer']=payload;diag={'enabled':True,'cache_hit':False,'prompt_version':PROCEDURAL_PROMPT_VERSION,'assessment':assessment,'validation':deepcopy(c.validation),'finish_reason':payload.get('finish_reason')};result['procedural_answer']=diag
 if valid:
  store['memory'].pending_goal.status='complete';result['state_after']=deepcopy(store['memory'].to_dict());store.setdefault(cache,{})[key]={'answer':deepcopy(payload),'diagnostic':deepcopy(diag)};return result,c.last_provider_result
 recovery={**assessment,'status':'partial','generation_allowed':False,'internal_knowledge_candidate':True,'reasons':[*(assessment.get('reasons') or []),'documented_answer_validation_failed']};result['procedural_recovery']={'attempted':True,'previous_mode':a.mode,'target_mode':'controlled_internal_knowledge'};result,trace=_internal(result,message,gateway,budget,store,model,recovery);return result,[c.last_provider_result,trace]
