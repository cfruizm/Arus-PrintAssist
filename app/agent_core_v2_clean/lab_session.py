from __future__ import annotations
from copy import deepcopy
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway
from .models import ConversationMemory
from .understanding import ConversationUnderstanding
from .policy import ConversationPolicy
from .response import NaturalResponseComposer
from .agent import CleanConversationalAgent
KEY="agent_core_v2_clean_store"
def get_store(session):
 if KEY not in session:session[KEY]={"memory":ConversationMemory(),"messages":[],"turns":[],"errors":[]}
 return session[KEY]
def reset_store(session):session.pop(KEY,None);return get_store(session)
def build_agent(secrets,session):
 gateway=LLMGateway(load_gateway_config(secrets),session)
 return CleanConversationalAgent(ConversationUnderstanding(gateway,int(secrets.get("V2_CLEAN_UNDERSTANDING_TOKENS",360))),ConversationPolicy(),NaturalResponseComposer(gateway,int(secrets.get("V2_CLEAN_RESPONSE_TOKENS",260))))
def process_message(message,secrets,session):
 store=get_store(session);store["messages"].append({"role":"user","content":message})
 try:
  result=build_agent(secrets,session).process(message,store["memory"]);text=result["answer"]["text"]
 except Exception as exc:
  store["errors"].append({"message":message,"error":f"{type(exc).__name__}: {exc}"});text="No pude procesar este turno. Intenta nuevamente.";result={"input":message,"error":str(exc),"production_changed":False}
 store["messages"].append({"role":"assistant","content":text});store["turns"].append(result);return result
def export_session(session):
 s=get_store(session);return {"format":"agent_core_v2_clean_conversational_foundation","messages":deepcopy(s["messages"]),"turns":deepcopy(s["turns"]),"state":s["memory"].to_dict(),"errors":deepcopy(s["errors"]),"retrieval_enabled":False,"production_changed":False}
