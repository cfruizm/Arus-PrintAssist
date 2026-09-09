from __future__ import annotations
from copy import deepcopy
from .procedural_answer import ProceduralAnswerComposer,fingerprint,PROMPT_VERSION

def maybe_generate_procedural(result,message,gateway,budget,store,model=""):
 u=result.get("understanding") or {};r=result.get("retrieval") or {}
 if u.get("intent")!="procedural":return result,None
 exp=r.get("procedural_expansion") or {}
 if not (r.get("ok") and exp.get("ok") and exp.get("same_document_only") and exp.get("ordered")):return result,None
 key=fingerprint(message,u,r,model);cache=store.setdefault("procedural_answer_cache",{});cached=cache.get(key)
 if cached:
  result["answer"]=deepcopy(cached["answer"]);result["procedural_answer"]={**deepcopy(cached["diagnostic"]),"cache_hit":True};store["cache_metrics"]["procedural_answer_hits"]+=1;return result,{"skipped":True,"reason":"procedural_answer_cache"}
 # Estimate now matches the observed prompt plus the expanded quality budget.
 allowed,reason=budget.can_call(store["telemetry"],estimated_tokens=2700)
 if not allowed:
  result["procedural_answer"]={"enabled":True,"cache_hit":False,"generation_blocked":True,"block_reason":reason,"prompt_version":PROMPT_VERSION};return result,{"skipped":True,"reason":"procedural_budget_block","block_reason":reason}
 composer=ProceduralAnswerComposer(gateway,900);answer=composer.compose(message,u,r);payload=answer.to_dict();payload.update({"documented_evidence_used":answer.mode=="procedural_documented_answer","internal_knowledge_used":False,"knowledge_mode":"documented_only" if answer.mode=="procedural_documented_answer" else "none"});result["answer"]=payload;diag={"enabled":True,"cache_hit":False,"prompt_version":PROMPT_VERSION,"evidence_count":len(r.get("evidence") or []),"pages":exp.get("pages") or [],"same_document_only":True,"quality_budget_preserved":True,"max_completion_tokens":900,"validation":deepcopy(composer.validation),"finish_reason":payload.get("finish_reason")};result["procedural_answer"]=diag
 if answer.mode=="procedural_documented_answer":store["memory"].pending_goal.status="complete";result["state_after"]=deepcopy(store["memory"].to_dict());cache[key]={"answer":deepcopy(payload),"diagnostic":deepcopy(diag)}
 return result,composer.last_provider_result
