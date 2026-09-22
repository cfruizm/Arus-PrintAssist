from __future__ import annotations
from copy import deepcopy
import secrets
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway, reset_gateway_session
from .models import ConversationMemory
from .budget import BudgetPolicy
from .telemetry import empty,normalize,add_result,snapshot
from .agent import CleanConversationalAgent

KEY="agent_core_v2_clean_store"

def get_store(s):
    if KEY not in s:
        s[KEY]={"session_id":secrets.token_hex(12),"memory":ConversationMemory(),"messages":[],"turns":[],"errors":[],"telemetry":empty(),"budget":BudgetPolicy.for_mode("normal").to_dict(),"retrieval_cache":{},"answer_context":{}}
    x=s[KEY];x["telemetry"]=normalize(x.get("telemetry"));x.setdefault("errors",[]);x.setdefault("turns",[]);x.setdefault("messages",[]);x.setdefault("retrieval_cache",{});return x

def reset_store(s):reset_gateway_session(s);s.pop(KEY,None);return get_store(s)

def _gateway(secrets_obj,s):return LLMGateway(load_gateway_config(secrets_obj),s)

def build_agent(secrets_obj,s,budget):return CleanConversationalAgent(_gateway(secrets_obj,s),budget)

def process_message(message,secrets_obj,s):
    store=get_store(s);budget=BudgetPolicy(**{k:v for k,v in store["budget"].items() if k in BudgetPolicy.__dataclass_fields__})
    before=deepcopy(store["memory"]);store["messages"].append({"role":"user","content":str(message)})
    try:
        result=build_agent(secrets_obj,s,budget).process(str(message),store["memory"])
        add_result(store["telemetry"],result["provider_trace"]["understanding"])
        add_result(store["telemetry"],result["provider_trace"]["response"])
        result["telemetry_after_turn"]=snapshot(store["telemetry"]);result["execution"]={"production_changed":False}
        store["turns"].append(result);store["messages"].append({"role":"assistant","content":result["answer"]["text"]});return result
    except Exception as exc:
        store["memory"]=before;item={"input":str(message),"error":{"type":type(exc).__name__,"message":str(exc)},"answer":{"text":"No pude procesar este turno. Conservé el estado anterior.","mode":"error"},"production_changed":False};store["errors"].append(item["error"]);store["turns"].append(item);store["messages"].append({"role":"assistant","content":item["answer"]["text"]});return item

def export_session(s):
    x=get_store(s);return {"format":"agent_core_v2_clean_minimal","production_changed":False,"session_id":x["session_id"],"memory":x["memory"].to_dict(),"turns":deepcopy(x["turns"]),"telemetry":snapshot(x["telemetry"]),"errors":deepcopy(x["errors"])}
