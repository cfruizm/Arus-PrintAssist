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
 if KEY not in s:s[KEY]={"memory":ConversationMemory(),"messages":[],"turns":[],"errors":[],"telemetry":empty(),"budget":BudgetPolicy().to_dict()}
 return s[KEY]
def reset_store(s):s.pop(KEY,None);return get_store(s)
def build_agent(secrets,s):
 g=LLMGateway(load_gateway_config(secrets),s)
 return CleanConversationalAgent(ConversationUnderstanding(g,int(secrets.get("V2_CLEAN_UNDERSTANDING_TOKENS",180))),ConversationPolicy(),NaturalResponseComposer(g,int(secrets.get("V2_CLEAN_RESPONSE_TOKENS",120))))
def process_message(message,secrets,s):
 store=get_store(s);store["messages"].append({"role":"user","content":message});budget=BudgetPolicy(**store["budget"]);allowed,reason=budget.can_call(store["telemetry"])
 if not allowed:
  text="Laboratorio pausado para proteger el presupuesto de tokens. El mensaje quedó registrado, pero no se llamó al LLM."
  result={"input":message,"state_before":store["memory"].to_dict(),"state_after":store["memory"].to_dict(),"decision":{"action":"budget_pause","reason":reason},"answer":{"text":text,"mode":"budget_pause","knowledge_used":False},"provider_trace":{"understanding":{"skipped":True,"reason":reason},"response":{"skipped":True,"reason":reason}},"turn_metrics":{"calls":0,"total_tokens":0,"failed_calls":0},"production_changed":False}
 else:
  try:
   result=build_agent(secrets,s).process(message,store["memory"]);text=result["answer"]["text"];trace=result.get("provider_trace") or {};add_result(store["telemetry"],trace.get("understanding"));add_result(store["telemetry"],trace.get("response"));result["turn_metrics"]=turn_metrics(trace.get("understanding"),trace.get("response"));result["session_metrics_after_turn"]=snapshot(store["telemetry"])
  except Exception as exc:
   store["errors"].append({"turn":store["memory"].turn_number+1,"message":message,"error_type":type(exc).__name__,"error":str(exc)});text="No pude procesar este turno. El error quedó registrado.";result={"input":message,"error":{"type":type(exc).__name__,"message":str(exc)},"production_changed":False}
 store["messages"].append({"role":"assistant","content":text});store["turns"].append(result);return result
def run_dry_scenario(session,outputs,messages):
 from .dry_run import DryRunUnderstanding,DryRunResponse
 store=get_store(session);agent=CleanConversationalAgent(DryRunUnderstanding(outputs),ConversationPolicy(),DryRunResponse());results=[]
 for message in messages:
  result=agent.process(message,store["memory"]);result["turn_metrics"]={"calls":0,"total_tokens":0,"failed_calls":0};store["messages"] += [{"role":"user","content":message},{"role":"assistant","content":result["answer"]["text"]}];store["turns"].append(result);results.append(result)
 return results
def export_session(s):
 x=get_store(s);return {"format":"agent_core_v2_clean_budgeted_diagnostic","messages":deepcopy(x["messages"]),"turns":deepcopy(x["turns"]),"state":x["memory"].to_dict(),"budget":deepcopy(x["budget"]),"telemetry":snapshot(x["telemetry"]),"errors":deepcopy(x["errors"]),"retrieval_enabled":False,"production_changed":False}
