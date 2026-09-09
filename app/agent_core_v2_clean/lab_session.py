from copy import deepcopy
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from .models import ConversationMemory
from .understanding import ConversationUnderstanding
from .policy import ConversationPolicy
from .response import NaturalResponseComposer
from .agent import CleanConversationalAgent
from .telemetry import empty,add_result,turn_metrics,snapshot
KEY="agent_core_v2_clean_store"
def get_store(s):
 if KEY not in s:s[KEY]={"memory":ConversationMemory(),"messages":[],"turns":[],"errors":[],"telemetry":empty()}
 return s[KEY]
def reset_store(s):s.pop(KEY,None);return get_store(s)
def build_agent(secrets,s):
 g=LLMGateway(load_gateway_config(secrets),s);return CleanConversationalAgent(ConversationUnderstanding(g,int(secrets.get("V2_CLEAN_UNDERSTANDING_TOKENS",300))),ConversationPolicy(),NaturalResponseComposer(g,int(secrets.get("V2_CLEAN_RESPONSE_TOKENS",180))))
def process_message(message,secrets,s):
 store=get_store(s);store["messages"].append({"role":"user","content":message})
 try:
  result=build_agent(secrets,s).process(message,store["memory"]);text=result["answer"]["text"]
  trace=result.get("provider_trace") or {};add_result(store["telemetry"],trace.get("understanding"));add_result(store["telemetry"],trace.get("response"));result["turn_metrics"]=turn_metrics(trace.get("understanding"),trace.get("response"));result["session_metrics_after_turn"]=snapshot(store["telemetry"])
 except Exception as exc:
  store["errors"].append({"turn":store["memory"].turn_number+1,"message":message,"error_type":type(exc).__name__,"error":str(exc)});text="No pude procesar este turno. El error quedó registrado en el diagnóstico.";result={"input":message,"error":{"type":type(exc).__name__,"message":str(exc)},"production_changed":False}
 store["messages"].append({"role":"assistant","content":text});store["turns"].append(result);return result
def export_session(s):
 x=get_store(s);return {"format":"agent_core_v2_clean_conversational_foundation_diagnostic","messages":deepcopy(x["messages"]),"turns":deepcopy(x["turns"]),"state":x["memory"].to_dict(),"telemetry":snapshot(x["telemetry"]),"errors":deepcopy(x["errors"]),"retrieval_enabled":False,"production_changed":False}
