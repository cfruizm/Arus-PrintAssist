from copy import deepcopy
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from .models import ConversationMemory
from .understanding import ConversationUnderstanding
from .policy import ConversationPolicy
from .response import NaturalResponseComposer
from .agent import CleanConversationalAgent
from .telemetry import empty,add_result,turn_metrics,snapshot
from .budget import BudgetPolicy
KEY="agent_core_v2_clean_store"
def get_store(s):
 if KEY not in s:s[KEY]={"memory":ConversationMemory(),"messages":[],"turns":[],"errors":[],"telemetry":empty(),"budget":BudgetPolicy.for_mode("normal").to_dict(),"deterministic_results":[]}
 return s[KEY]
def reset_store(s):s.pop(KEY,None);return get_store(s)
def build_agent(secrets,s,budget):
 g=LLMGateway(load_gateway_config(secrets),s)
 # The selected mode is authoritative. Old token secrets cannot silently override it.
 return CleanConversationalAgent(ConversationUnderstanding(g,budget.understanding_max_tokens),ConversationPolicy(),NaturalResponseComposer(g,budget.response_max_tokens))
def process_message(message,secrets,s):
 store=get_store(s);budget=BudgetPolicy(**store["budget"]);allowed,reason=budget.can_call(store["telemetry"])
 if not allowed:return {"input":message,"blocked":True,"decision":{"action":"budget_block","reason":reason},"answer":{"text":"La prueba no se ejecutó porque alcanzaría el presupuesto configurado.","mode":"budget_block","knowledge_used":False},"turn_metrics":{"calls":0,"total_tokens":0},"production_changed":False}
 store["messages"].append({"role":"user","content":message})
 try:
  result=build_agent(secrets,s,budget).process(message,store["memory"]);text=result["answer"]["text"];trace=result.get("provider_trace") or {};contract=(result.get("understanding_contract") or {}).get("valid")
  add_result(store["telemetry"],trace.get("understanding"),contract);add_result(store["telemetry"],trace.get("response"));result["turn_metrics"]=turn_metrics(trace.get("understanding"),trace.get("response"),contract);result["session_metrics_after_turn"]=snapshot(store["telemetry"])
 except Exception as exc:
  store["errors"].append({"turn":store["memory"].turn_number+1,"message":message,"error_type":type(exc).__name__,"error":str(exc)});text="No pude procesar este turno. El error quedó registrado.";result={"input":message,"error":{"type":type(exc).__name__,"message":str(exc)},"production_changed":False}
 store["messages"].append({"role":"assistant","content":text});store["turns"].append(result);return result
def export_session(s):
 x=get_store(s);return {"format":"agent_core_v2_clean_contract_diagnostic","messages":deepcopy(x["messages"]),"turns":deepcopy(x["turns"]),"state":x["memory"].to_dict(),"budget":deepcopy(x["budget"]),"telemetry":snapshot(x["telemetry"]),"deterministic_results":deepcopy(x.get("deterministic_results",[])),"errors":deepcopy(x["errors"]),"retrieval_enabled":False,"production_changed":False}
