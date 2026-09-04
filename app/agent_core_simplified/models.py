from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any
@dataclass
class Entity: kind:str;canonical_id:str;name:str;mention:str="";confidence:float=.0
@dataclass
class Attempt: action:str;result:str|None=None
@dataclass
class Topic:
 topic_id:str="topic-1";products:list[Entity]=field(default_factory=list);components:list[Entity]=field(default_factory=list);processes:list[Entity]=field(default_factory=list);request_kind:str="none"
@dataclass
class Case:
 status:str="idle";symptoms:list[str]=field(default_factory=list);details:list[dict[str,Any]]=field(default_factory=list);attempts:list[Attempt]=field(default_factory=list);affected_scope:str|None=None;resolution_status:str|None=None
@dataclass
class Escalation:
 status:str="inactive";collected:dict[str,Any]=field(default_factory=dict);missing_fields:list[str]=field(default_factory=list)
@dataclass
class ConversationState:
 conversation_id:str="local";turn_number:int=0;active_topic:Topic=field(default_factory=Topic);case:Case=field(default_factory=Case);escalation:Escalation=field(default_factory=Escalation);topic_history:list[dict[str,Any]]=field(default_factory=list)
 def to_dict(self):return asdict(self)
@dataclass
class TurnPlan:
 topic_relation:str="same";entities:list[dict[str,Any]]=field(default_factory=list);symptoms:list[str]=field(default_factory=list);details:list[dict[str,Any]]=field(default_factory=list);attempt:str|None=None;attempt_result:str|None=None;request_kind:str="none";needs_documents:bool=False;escalation_action:str="none";confidence:float=.0
 def to_dict(self):return asdict(self)
