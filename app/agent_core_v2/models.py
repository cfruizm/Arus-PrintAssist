from dataclasses import dataclass,field,asdict
from typing import Any
@dataclass
class EntityRef:
 kind:str;canonical_id:str;canonical_name:str;matched_text:str="";confidence:float=1.;source:str="registry"
@dataclass
class Attempt: action:str;result:str|None=None;turn_added:int=0
@dataclass
class TopicState:
 topic_id:str="topic-1";products:list[EntityRef]=field(default_factory=list);components:list[EntityRef]=field(default_factory=list);processes:list[EntityRef]=field(default_factory=list);intent:str|None=None
@dataclass
class TechnicalCase:
 status:str="idle";symptoms:list[str]=field(default_factory=list);attempts:list[Attempt]=field(default_factory=list);affected_scope:str|None=None;evidence:list[str]=field(default_factory=list);resolution_status:str|None=None
@dataclass
class EscalationState: status:str="inactive";pending_field:str|None=None;collected_fields:dict[str,Any]=field(default_factory=dict);suspended_reason:str|None=None
@dataclass
class ConversationState:
 conversation_id:str="local";mode:str="support";active_topic:TopicState=field(default_factory=TopicState);technical_case:TechnicalCase=field(default_factory=TechnicalCase);escalation:EscalationState=field(default_factory=EscalationState);last_action:str|None=None;turn_number:int=0;topic_history:list[dict]=field(default_factory=list)
 def to_dict(self):return asdict(self)
@dataclass
class InterpreterProposal:
 conversation_act:str;intent:str;requested_action:str;topic_relation:str="unknown";entities:list[dict]=field(default_factory=list);facts:list[dict]=field(default_factory=list);clarification_question:str|None=None;confidence:float=0.;reasoning_summary:str=""
@dataclass
class CanonicalDecision:
 action:str;intent:str;conversation_act:str;topic_relation:str;entities:list[EntityRef]=field(default_factory=list);facts:list[dict]=field(default_factory=list);clarification_question:str|None=None;confidence:float=0.;reasons:list[str]=field(default_factory=list);state_mutation_allowed:bool=False;requires_retrieval:bool=False
 def to_dict(self):return asdict(self)
@dataclass
class EvidenceItem:
 id:str;title:str;url:str;text:str;metadata:dict=field(default_factory=dict);retrieval_score:float=0.;identity_score:float=0.;intent_score:float=0.;topic_score:float=0.;applicability_score:float=0.;eligible:bool=False;citable:bool=False;rejection_reasons:list[str]=field(default_factory=list)
 def to_dict(self):return asdict(self)
@dataclass
class TurnResult:
 input:str;state_before:dict;proposal:dict;decision:dict;state_after:dict;response_directive:dict;audit:dict;evidence:dict=field(default_factory=dict);answer:dict=field(default_factory=dict)
 def to_dict(self):return asdict(self)
