import json,sys,types
from dataclasses import dataclass
@dataclass
class LLMRequest:
 messages:list;purpose:str="";max_tokens:int=0;temperature:float=0.;response_schema:dict|None=None
_stub=types.ModuleType("app.llm_gateway.models");_stub.LLMRequest=LLMRequest
sys.modules.setdefault("app.llm_gateway",types.ModuleType("app.llm_gateway"));sys.modules["app.llm_gateway.models"]=_stub
from types import SimpleNamespace
from app.agent_core_v2_clean.understanding import ConversationUnderstanding
from app.agent_core_v2_clean.memory import apply_understanding
from app.agent_core_v2_clean.models import ConversationMemory

class Gateway:
 def __init__(self,payload):self.payload=payload
 def complete(self,request):
  return SimpleNamespace(ok=True,text=json.dumps(self.payload),error_code=None,to_dict=lambda:{"ok":True,"text":json.dumps(self.payload),"purpose":"test","usage":{},"metadata":{}})

def payload(**overrides):
 x={"user_act":"new_request","intent":"conceptual","topic_relation":"new_topic","domain_relevance":"in_scope","current_goal":"Explicar herramienta de impresión","goal_complete":False,"goal_updates":{"producto":"Herramienta de impresión"},"case_updates":[],"needs_clarification":False,"clarification_target":None,"should_retrieve":True,"confidence":.95,"reasoning_summary":"solicitud clara"};x.update(overrides);return x

def test_first_turn_answer_to_question_is_reconciled_without_damaging_goal():
 u=ConversationUnderstanding(Gateway(payload(user_act="answer_to_question")),300);m=ConversationMemory();x=u.interpret("Explicar herramienta de impresión",m)
 assert x.user_act=="new_request" and x.topic_relation=="new_topic" and u.contract_valid

def test_new_topic_removes_unanchored_inherited_entity():
 m=ConversationMemory(active_topic="Tema anterior");m.pending_goal.summary="Tema anterior";m.pending_goal.known_details={"producto":"Plataforma anterior"}
 raw=payload(intent="procedural",current_goal="Realizar distribución de facturación con template",goal_updates={"producto":"Plataforma anterior","tema":"distribución de facturación con template"})
 u=ConversationUnderstanding(Gateway(raw),300);x=u.interpret("Cómo realizar distribución de facturación con template",m);apply_understanding(m,x)
 assert "Plataforma anterior" not in str(m.pending_goal.known_details) and m.topic_history[0]["topic"]=="Tema anterior"

def test_same_topic_keeps_grounded_atomic_details():
 m=ConversationMemory(active_topic="Configurar acceso");m.pending_goal.summary="Configurar acceso";m.last_assistant_question="¿Para cuál alcance?"
 raw=payload(user_act="answer_to_question",intent="procedural",topic_relation="same_topic",current_goal="Configurar acceso para usuario específico",goal_updates={"alcance":"usuario específico"})
 u=ConversationUnderstanding(Gateway(raw),300);x=u.interpret("Para usuario específico",m);apply_understanding(m,x)
 assert m.pending_goal.known_details["alcance"]=="usuario específico"

def test_degraded_output_preserves_previous_state():
 m=ConversationMemory(active_topic="Caso activo");m.pending_goal.summary="Resolver caso"
 u=ConversationUnderstanding(Gateway({}),300);x=u.interpret("mensaje",m);before=(m.active_topic,m.pending_goal.summary);apply_understanding(m,x)
 assert (m.active_topic,m.pending_goal.summary)==before and x.degraded
