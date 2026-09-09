from __future__ import annotations
from copy import deepcopy
from .procedural_answer import ProceduralAnswerComposer,fingerprint as procedural_fingerprint,PROMPT_VERSION as PROCEDURAL_PROMPT_VERSION
from .evidence_sufficiency import assess_procedural_evidence
from .internal_knowledge import ControlledInternalKnowledgeComposer,fingerprint as internal_fingerprint,PROMPT_VERSION as INTERNAL_PROMPT_VERSION

def _valid_cached(item):
 a=(item or {}).get("answer") or {};return a.get("mode") in {"procedural_documented_answer","controlled_internal_knowledge"} and str(a.get("finish_reason") or "").casefold() not in {"length","max_tokens"}
def _get_cache(store,name,key):
 item=store.setdefault(name,{}).get(key)
 if item and not _valid_cached(item):store[name].pop(key,None);return None
 return item
def _internal(result,message,gateway,budget,store,model,assessment):
 u=result.get("understanding") or {};r=result.get("retrieval") or {};key=internal_fingerprint(message,u,r,assessment,model);cache="internal_knowledge_cache";store.setdefault(cache,{});store.setdefault("cache_metrics",{}).setdefault("internal_knowledge_hits",0);cached=_get_cache(store,cache,key)
 if cached:
  result["answer"]=deepcopy(cached["answer"]);result["internal_knowledge"]={**deepcopy(cached["diagnostic"]),"cache_hit":True};store["cache_metrics"]["internal_knowledge_hits"]+=1;return result,{"skipped":True,"reason":"internal_knowledge_cache"}
 allowed,reason=budget.can_call(store["telemetry"],estimated_tokens=1800)
 if not allowed:
  result["internal_knowledge"]={"enabled":True,"generation_blocked":True,"block_reason":reason,"assessment":assessment};return result,{"skipped":True,"reason":"internal_knowledge_budget_block"}
 composer=ControlledInternalKnowledgeComposer(gateway,520);answer=composer.compose(message,u,r,assessment);payload=answer.to_dict();valid=answer.mode=="controlled_internal_knowledge";payload.update({"documented_evidence_used":bool(assessment.get("usable_chunks")),"internal_knowledge_used":valid,"knowledge_mode":"documented_plus_internal" if valid and assessment.get("usable_chunks") else "internal_only" if valid else "none"});result["answer"]=payload;diag={"enabled":True,"cache_hit":False,"prompt_version":INTERNAL_PROMPT_VERSION,"trigger_status":assessment.get("status"),"trigger_reasons":assessment.get("reasons"),"validation":deepcopy(composer.validation)};result["internal_knowledge"]=diag
 if valid:store["memory"].pending_goal.status="complete";result["state_after"]=deepcopy(store["memory"].to_dict());store[cache][key]={"answer":deepcopy(payload),"diagnostic":deepcopy(diag)}
 return result,composer.last_provider_result

def maybe_generate_procedural(result,message,gateway,budget,store,model=""):
 u=result.get("understanding") or {};r=result.get("retrieval") or {}
 if u.get("intent")!="procedural":return result,None
 assessment=assess_procedural_evidence(r).to_dict();result["evidence_sufficiency"]=assessment
 if assessment["status"]!="sufficient":return _internal(result,message,gateway,budget,store,model,assessment)
 key=procedural_fingerprint(message,u,r,model);cache="procedural_answer_cache";store.setdefault(cache,{});store.setdefault("cache_metrics",{}).setdefault("procedural_answer_hits",0);cached=_get_cache(store,cache,key)
 if cached:
  result["answer"]=deepcopy(cached["answer"]);result["procedural_answer"]={**deepcopy(cached["diagnostic"]),"cache_hit":True};store["cache_metrics"]["procedural_answer_hits"]+=1;return result,{"skipped":True,"reason":"procedural_answer_cache"}
 allowed,reason=budget.can_call(store["telemetry"],estimated_tokens=2700)
 if not allowed:return result,{"skipped":True,"reason":"procedural_budget_block","block_reason":reason}
 composer=ProceduralAnswerComposer(gateway,900);answer=composer.compose(message,u,r);payload=answer.to_dict();valid=answer.mode=="procedural_documented_answer";payload.update({"documented_evidence_used":valid,"internal_knowledge_used":False,"knowledge_mode":"documented_only" if valid else "none"});result["answer"]=payload;diag={"enabled":True,"cache_hit":False,"prompt_version":PROCEDURAL_PROMPT_VERSION,"assessment":assessment,"validation":deepcopy(composer.validation),"finish_reason":payload.get("finish_reason")};result["procedural_answer"]=diag
 if valid:store["memory"].pending_goal.status="complete";result["state_after"]=deepcopy(store["memory"].to_dict());store[cache][key]={"answer":deepcopy(payload),"diagnostic":deepcopy(diag)}
 return result,composer.last_provider_result
