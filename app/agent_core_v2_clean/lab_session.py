from copy import deepcopy
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from .models import ConversationMemory
from .understanding import ConversationUnderstanding
from .policy import ConversationPolicy
from .response import NaturalResponseComposer
from .agent import CleanConversationalAgent
from .telemetry import empty,normalize,add_result,turn_metrics,snapshot
from .budget import BudgetPolicy
KEY="agent_core_v2_clean_store"
def _context_key(message,memory):return "|".join((" ".join(str(message).split()).casefold(),str(memory.active_topic or "").strip().casefold(),str(memory.pending_goal.summary or "").strip().casefold()))
def _artifact(result):return {k:deepcopy(result.get(k)) for k in ("understanding","understanding_contract","goal_update_normalization","decision","answer","retrieval")}
def get_store(s):
 if KEY not in s:s[KEY]={"memory":ConversationMemory(),"messages":[],"turns":[],"errors":[],"telemetry":empty(),"budget":BudgetPolicy.for_mode("normal").to_dict(),"deterministic_results":[],"exact_turn_cache":{},"cache_metrics":{"hits":0,"calls_avoided":0,"tokens_avoided_estimate":0}}
 x=s[KEY];x["telemetry"]=normalize(x.get("telemetry"));x.setdefault("exact_turn_cache",{});x.setdefault("cache_metrics",{"hits":0,"calls_avoided":0,"tokens_avoided_estimate":0});x.setdefault("deterministic_results",[]);x.setdefault("errors",[]);x.setdefault("turns",[]);x.setdefault("messages",[]);return x
def reset_store(s):s.pop(KEY,None);return get_store(s)
def build_agent(secrets,s,budget):
 g=LLMGateway(load_gateway_config(secrets),s);return CleanConversationalAgent(ConversationUnderstanding(g,budget.understanding_max_tokens),ConversationPolicy(),NaturalResponseComposer(g,budget.response_max_tokens))
def process_message(message,secrets,s):
 store=get_store(s);budget=BudgetPolicy(**store["budget"]);before=deepcopy(store["memory"].to_dict());key_before=_context_key(message,store["memory"]);cached=store["exact_turn_cache"].get(key_before)
 execution={"mode":budget.mode,"understanding_budget":budget.understanding_max_tokens,"response_budget":budget.response_max_tokens}
 if cached:
  store["memory"].turn_number+=1;after=deepcopy(store["memory"].to_dict());estimate=int(cached.get("tokens_estimate") or 0);store["cache_metrics"]["hits"]+=1;store["cache_metrics"]["calls_avoided"]+=1;store["cache_metrics"]["tokens_avoided_estimate"]+=estimate
  result={"input":message,"state_before":before,**deepcopy(cached["artifact"]),"state_after":after,"provider_trace":{"understanding":{"skipped":True,"reason":"exact_turn_cache"},"response":{"skipped":True,"reason":"exact_turn_cache"}},"turn_metrics":{"calls":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0,"provider_failed_calls":0,"contract_failed_calls":0,"functional_failed_calls":0},"session_metrics_after_turn":snapshot(store["telemetry"]),"execution":{**execution,"cache_hit":True},"cache":{"hit":True,"type":"exact_turn","calls_avoided":1,"tokens_avoided_estimate":estimate},"production_changed":False}
  text=result["answer"]["text"];store["messages"] += [{"role":"user","content":message},{"role":"assistant","content":text}];store["turns"].append(result);return result
 allowed,reason=budget.can_call(store["telemetry"])
 if not allowed:return {"input":message,"blocked":True,"decision":{"action":"budget_block","reason":reason},"answer":{"text":"La prueba no se ejecutó porque alcanzaría el presupuesto configurado.","mode":"budget_block","knowledge_used":False},"turn_metrics":{"calls":0,"total_tokens":0},"execution":execution,"production_changed":False}
 store["messages"].append({"role":"user","content":message})
 try:
  result=build_agent(secrets,s,budget).process(message,store["memory"]);text=result["answer"]["text"];trace=result.get("provider_trace") or {};contract=(result.get("understanding_contract") or {}).get("valid");add_result(store["telemetry"],trace.get("understanding"),contract);add_result(store["telemetry"],trace.get("response"));result["turn_metrics"]=turn_metrics(trace.get("understanding"),trace.get("response"),contract);result["session_metrics_after_turn"]=snapshot(store["telemetry"]);result["execution"]={**execution,"cache_hit":False};result["cache"]={"hit":False,"type":None,"calls_avoided":0,"tokens_avoided_estimate":0}
  if contract:
   entry={"artifact":_artifact(result),"tokens_estimate":result["turn_metrics"].get("total_tokens",0)};store["exact_turn_cache"][key_before]=entry;store["exact_turn_cache"][_context_key(message,store["memory"])]=entry
 except Exception as exc:
  store["errors"].append({"turn":store["memory"].turn_number+1,"message":message,"error_type":type(exc).__name__,"error":str(exc)});text="No pude procesar este turno. El error quedó registrado.";result={"input":message,"error":{"type":type(exc).__name__,"message":str(exc)},"execution":execution,"production_changed":False}
 store["messages"].append({"role":"assistant","content":text});store["turns"].append(result);return result
def export_session(s):
 x=get_store(s);return {"format":"agent_core_v2_clean_cache_consistency","messages":deepcopy(x["messages"]),"turns":deepcopy(x["turns"]),"state":x["memory"].to_dict(),"budget":deepcopy(x["budget"]),"telemetry":snapshot(x["telemetry"]),"cache_metrics":deepcopy(x["cache_metrics"]),"deterministic_results":deepcopy(x.get("deterministic_results",[])),"errors":deepcopy(x["errors"]),"retrieval_enabled":False,"production_changed":False}
