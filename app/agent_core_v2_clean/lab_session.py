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
from .retrieval import RetrievalQueryBuilder,ReadOnlyRetrieval,retrieval_summary
from .documented_answer import DocumentedAnswerComposer
KEY="agent_core_v2_clean_store"
def _context_key(message,memory):return "|".join((" ".join(str(message).split()).casefold(),str(memory.active_topic or "").strip().casefold(),str(memory.pending_goal.summary or "").strip().casefold()))
def _artifact(result):return {k:deepcopy(result.get(k)) for k in ("understanding","understanding_contract","goal_update_normalization","decision","answer","retrieval")}
def get_store(s):
 if KEY not in s:s[KEY]={"memory":ConversationMemory(),"messages":[],"turns":[],"errors":[],"telemetry":empty(),"budget":BudgetPolicy.for_mode("normal").to_dict(),"deterministic_results":[],"exact_turn_cache":{},"retrieval_cache":{},"cache_metrics":{"hits":0,"calls_avoided":0,"tokens_avoided_estimate":0,"retrieval_hits":0}}
 x=s[KEY];x["telemetry"]=normalize(x.get("telemetry"));x.setdefault("exact_turn_cache",{});x.setdefault("retrieval_cache",{});x.setdefault("cache_metrics",{"hits":0,"calls_avoided":0,"tokens_avoided_estimate":0,"retrieval_hits":0});x["cache_metrics"].setdefault("retrieval_hits",0);x.setdefault("deterministic_results",[]);x.setdefault("errors",[]);x.setdefault("turns",[]);x.setdefault("messages",[]);return x
def reset_store(s):s.pop(KEY,None);return get_store(s)
def _gateway(secrets,s):return LLMGateway(load_gateway_config(secrets),s)
def build_agent(secrets,s,budget):
 g=_gateway(secrets,s);return CleanConversationalAgent(ConversationUnderstanding(g,budget.understanding_max_tokens),ConversationPolicy(),NaturalResponseComposer(g,budget.response_max_tokens))
def _attach_retrieval(result,message,store):
 if (result.get("decision") or {}).get("action")!="defer_to_retrieval":return result
 try:
  u=type("U",(),result.get("understanding") or {})();builder=RetrievalQueryBuilder();built=builder.build(message,store["memory"],u);current_only=builder.current_only(message,u);cached=store["retrieval_cache"].get(built.fingerprint)
  if cached:retrieval=deepcopy(cached);retrieval["cache_hit"]=True;store["cache_metrics"]["retrieval_hits"]+=1
  else:retrieval=ReadOnlyRetrieval(k=6).search(built,current_only);retrieval["cache_hit"]=False;store["retrieval_cache"][built.fingerprint]=deepcopy(retrieval)
 except Exception as exc:retrieval={"enabled":True,"ok":False,"llm_called":False,"production_changed":False,"diagnostic_only":True,"cache_hit":False,"count":0,"evidence":[],"document_groups":[],"errors":[{"type":type(exc).__name__,"message":str(exc),"stage":"retrieval_attachment"}]}
 result["retrieval"]=retrieval;result["answer"]["text"]=retrieval_summary(retrieval);result["answer"]["mode"]="retrieval_diagnostic" if retrieval.get("ok") else "retrieval_error";return result
def _generate_documented(result,message,secrets,s,budget,store):
 retrieval=result.get("retrieval") or {};intent=(result.get("understanding") or {}).get("intent")
 # Phase 2B gate: only conceptual answers with evidence. Procedures remain diagnostic until multipage evidence is ready.
 if intent!="conceptual" or not retrieval.get("ok") or not retrieval.get("evidence"):return result,None
 allowed,_=budget.can_call(store["telemetry"],estimated_tokens=700)
 if not allowed:return result,None
 composer=DocumentedAnswerComposer(_gateway(secrets,s),max_tokens=max(220,budget.response_max_tokens));answer=composer.compose(message,result.get("understanding") or {},retrieval);result["answer"]=answer.to_dict();result["documented_answer"]={"enabled":True,"intent_gate":"conceptual","evidence_count":len(retrieval.get("evidence") or []),"citation_guard":answer.mode in {"documented_answer","documented_citation_guard"}};return result,composer.last_provider_result
def process_message(message,secrets,s):
 store=get_store(s);budget=BudgetPolicy(**store["budget"]);before=deepcopy(store["memory"].to_dict());key_before=_context_key(message,store["memory"]);cached=store["exact_turn_cache"].get(key_before);execution={"mode":budget.mode,"understanding_budget":budget.understanding_max_tokens,"response_budget":budget.response_max_tokens}
 if cached:
  store["memory"].turn_number+=1;result={"input":message,"state_before":before,**deepcopy(cached["artifact"]),"state_after":deepcopy(store["memory"].to_dict()),"provider_trace":{"understanding":{"skipped":True,"reason":"exact_turn_cache"},"response":{"skipped":True,"reason":"exact_turn_cache"}},"execution":{**execution,"cache_hit":True},"cache":{"hit":True,"type":"exact_turn"},"production_changed":False};result,response_trace=_generate_documented(result,message,secrets,s,budget,store);result["provider_trace"]["documented_answer"]=response_trace or {"skipped":True,"reason":"documented_answer_not_called"};add_result(store["telemetry"],response_trace);result["turn_metrics"]=turn_metrics(None,response_trace);result["session_metrics_after_turn"]=snapshot(store["telemetry"]);text=result["answer"]["text"];store["cache_metrics"]["hits"]+=1;store["cache_metrics"]["calls_avoided"]+=1;store["messages"] += [{"role":"user","content":message},{"role":"assistant","content":text}];store["turns"].append(result);return result
 allowed,reason=budget.can_call(store["telemetry"])
 if not allowed:return {"input":message,"blocked":True,"answer":{"text":"La prueba no se ejecutó porque alcanzaría el presupuesto configurado.","mode":"budget_block","knowledge_used":False},"decision":{"action":"budget_block","reason":reason},"turn_metrics":{"calls":0,"total_tokens":0},"execution":execution,"production_changed":False}
 store["messages"].append({"role":"user","content":message})
 try:
  result=build_agent(secrets,s,budget).process(message,store["memory"]);result=_attach_retrieval(result,message,store);trace=result.get("provider_trace") or {};contract=(result.get("understanding_contract") or {}).get("valid");add_result(store["telemetry"],trace.get("understanding"),contract);add_result(store["telemetry"],trace.get("response"));result,doc_trace=_generate_documented(result,message,secrets,s,budget,store);result.setdefault("provider_trace",{})["documented_answer"]=doc_trace or {"skipped":True,"reason":"documented_answer_not_called"};add_result(store["telemetry"],doc_trace);result["turn_metrics"]=turn_metrics(trace.get("understanding"),doc_trace or trace.get("response"));result["session_metrics_after_turn"]=snapshot(store["telemetry"]);result["execution"]={**execution,"cache_hit":False};result["cache"]={"hit":False};text=result["answer"]["text"]
  if contract:
   entry={"artifact":_artifact(result),"tokens_estimate":result["turn_metrics"].get("total_tokens",0)};store["exact_turn_cache"][key_before]=entry;store["exact_turn_cache"][_context_key(message,store["memory"])]=entry
 except Exception as exc:store["errors"].append({"turn":store["memory"].turn_number+1,"message":message,"error_type":type(exc).__name__,"error":str(exc)});text="No pude procesar este turno. El error quedó registrado.";result={"input":message,"error":{"type":type(exc).__name__,"message":str(exc)},"execution":execution,"production_changed":False}
 store["messages"].append({"role":"assistant","content":text});store["turns"].append(result);return result
def export_session(s):
 x=get_store(s);return {"format":"agent_core_v2_clean_documented_answer","messages":deepcopy(x["messages"]),"turns":deepcopy(x["turns"]),"state":x["memory"].to_dict(),"budget":deepcopy(x["budget"]),"telemetry":snapshot(x["telemetry"]),"cache_metrics":deepcopy(x["cache_metrics"]),"errors":deepcopy(x["errors"]),"retrieval_enabled":True,"documented_answer_enabled":True,"production_changed":False}
