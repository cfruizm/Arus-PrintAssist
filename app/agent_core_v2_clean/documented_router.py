from __future__ import annotations
from copy import deepcopy
from .procedural_answer import ProceduralAnswerComposer,fingerprint as procedural_fingerprint,PROMPT_VERSION as PROCEDURAL_PROMPT_VERSION
from .evidence_sufficiency import assess_procedural_evidence
from .internal_knowledge import ControlledInternalKnowledgeComposer,fingerprint as internal_fingerprint,PROMPT_VERSION as INTERNAL_PROMPT_VERSION

def _cache_hit(result,store,key,cache_name,metric_name,diagnostic_name,reason):
    cached=store.setdefault(cache_name,{}).get(key)
    if not cached:return False,None
    result["answer"]=deepcopy(cached["answer"]);result[diagnostic_name]={**deepcopy(cached["diagnostic"]),"cache_hit":True};store["cache_metrics"][metric_name]+=1
    return True,{"skipped":True,"reason":reason}

def _internal(result,message,gateway,budget,store,model,assessment):
    u=result.get("understanding") or {};r=result.get("retrieval") or {};key=internal_fingerprint(message,u,r,assessment,model)
    store.setdefault("internal_knowledge_cache",{});store.setdefault("cache_metrics",{}).setdefault("internal_knowledge_hits",0)
    hit,trace=_cache_hit(result,store,key,"internal_knowledge_cache","internal_knowledge_hits","internal_knowledge","internal_knowledge_cache")
    if hit:return result,trace
    allowed,reason=budget.can_call(store["telemetry"],estimated_tokens=1500)
    if not allowed:
        result["internal_knowledge"]={"enabled":True,"generation_blocked":True,"block_reason":reason,"assessment":assessment,"prompt_version":INTERNAL_PROMPT_VERSION};return result,{"skipped":True,"reason":"internal_knowledge_budget_block","block_reason":reason}
    composer=ControlledInternalKnowledgeComposer(gateway,420);answer=composer.compose(message,u,r,assessment);payload=answer.to_dict();valid=answer.mode=="controlled_internal_knowledge";payload.update({"documented_evidence_used":bool(assessment.get("usable_chunks")),"internal_knowledge_used":valid,"knowledge_mode":"documented_plus_internal" if valid and assessment.get("usable_chunks") else "internal_only" if valid else "none"});result["answer"]=payload
    diag={"enabled":True,"cache_hit":False,"prompt_version":INTERNAL_PROMPT_VERSION,"trigger_status":assessment.get("status"),"warning_present":valid,"citations_for_internal_forbidden":True,"validation":deepcopy(composer.validation),"documented_excerpt_count":len(r.get("evidence") or [])}
    result["internal_knowledge"]=diag
    if valid:store["memory"].pending_goal.status="complete";result["state_after"]=deepcopy(store["memory"].to_dict());store["internal_knowledge_cache"][key]={"answer":deepcopy(payload),"diagnostic":deepcopy(diag)}
    return result,composer.last_provider_result

def maybe_generate_procedural(result,message,gateway,budget,store,model=""):
    u=result.get("understanding") or {};r=result.get("retrieval") or {}
    if u.get("intent")!="procedural":return result,None
    assessment=assess_procedural_evidence(r).to_dict();result["evidence_sufficiency"]=assessment
    if assessment["status"]!="sufficient":return _internal(result,message,gateway,budget,store,model,assessment)
    key=procedural_fingerprint(message,u,r,model);store.setdefault("procedural_answer_cache",{});store.setdefault("cache_metrics",{}).setdefault("procedural_answer_hits",0)
    hit,trace=_cache_hit(result,store,key,"procedural_answer_cache","procedural_answer_hits","procedural_answer","procedural_answer_cache")
    if hit:return result,trace
    allowed,reason=budget.can_call(store["telemetry"],estimated_tokens=2700)
    if not allowed:
        result["procedural_answer"]={"enabled":True,"generation_blocked":True,"block_reason":reason,"assessment":assessment,"prompt_version":PROCEDURAL_PROMPT_VERSION};return result,{"skipped":True,"reason":"procedural_budget_block","block_reason":reason}
    composer=ProceduralAnswerComposer(gateway,900);answer=composer.compose(message,u,r);payload=answer.to_dict();valid=answer.mode=="procedural_documented_answer";payload.update({"documented_evidence_used":valid,"internal_knowledge_used":False,"knowledge_mode":"documented_only" if valid else "none"});result["answer"]=payload
    diag={"enabled":True,"cache_hit":False,"prompt_version":PROCEDURAL_PROMPT_VERSION,"evidence_count":len(r.get("evidence") or []),"pages":list(dict.fromkeys((r.get("procedural_expansion") or {}).get("pages") or [])),"same_document_only":True,"quality_budget_preserved":True,"max_completion_tokens":900,"validation":deepcopy(composer.validation),"finish_reason":payload.get("finish_reason"),"assessment":assessment};result["procedural_answer"]=diag
    if valid:store["memory"].pending_goal.status="complete";result["state_after"]=deepcopy(store["memory"].to_dict());store["procedural_answer_cache"][key]={"answer":deepcopy(payload),"diagnostic":deepcopy(diag)}
    return result,composer.last_provider_result
