from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any,Literal

Intent=Literal["social","capabilities","support_intake","conceptual","procedural","troubleshooting","requirements","architecture","warranty","escalation","cancel","resume","out_of_scope","unknown"]
Action=Literal["respond_directly","ask_clarification","retrieve","record_case_detail","record_attempt","record_attempt_result","start_escalation","continue_escalation","suspend_escalation","resume_escalation","cancel_all","switch_topic","out_of_scope"]
TopicRelation=Literal["same_topic","new_topic","independent_question","unknown"]

@dataclass
class EntityRef:
    kind:str
    canonical_id:str
    canonical_name:str
    matched_text:str=""
    confidence:float=1.0
    source:str="registry"

@dataclass
class Attempt:
    action:str
    result:str|None=None
    turn_added:int=0

@dataclass
class TopicState:
    topic_id:str="topic-1"
    products:list[EntityRef]=field(default_factory=list)
    components:list[EntityRef]=field(default_factory=list)
    processes:list[EntityRef]=field(default_factory=list)
    intent:str|None=None

@dataclass
class TechnicalCase:
    status:str="idle"
    symptoms:list[str]=field(default_factory=list)
    attempts:list[Attempt]=field(default_factory=list)
    affected_scope:str|None=None
    evidence:list[str]=field(default_factory=list)
    resolution_status:str|None=None

@dataclass
class EscalationState:
    status:str="inactive"
    pending_field:str|None=None
    collected_fields:dict[str,Any]=field(default_factory=dict)
    suspended_reason:str|None=None

@dataclass
class ConversationState:
    conversation_id:str="local"
    mode:str="support"
    active_topic:TopicState=field(default_factory=TopicState)
    technical_case:TechnicalCase=field(default_factory=TechnicalCase)
    escalation:EscalationState=field(default_factory=EscalationState)
    last_action:str|None=None
    turn_number:int=0
    topic_history:list[dict[str,Any]]=field(default_factory=list)
    def to_dict(self):return asdict(self)

@dataclass
class InterpreterProposal:
    conversation_act:str
    intent:Intent
    requested_action:Action
    topic_relation:TopicRelation="unknown"
    entities:list[dict[str,Any]]=field(default_factory=list)
    facts:list[dict[str,Any]]=field(default_factory=list)
    clarification_question:str|None=None
    confidence:float=0.0
    reasoning_summary:str=""

@dataclass
class CanonicalDecision:
    action:Action
    intent:Intent
    conversation_act:str
    topic_relation:TopicRelation
    entities:list[EntityRef]=field(default_factory=list)
    facts:list[dict[str,Any]]=field(default_factory=list)
    clarification_question:str|None=None
    confidence:float=0.0
    reasons:list[str]=field(default_factory=list)
    state_mutation_allowed:bool=False
    requires_retrieval:bool=False
    def to_dict(self):return asdict(self)

@dataclass
class TurnResult:
    input:str
    state_before:dict[str,Any]
    proposal:dict[str,Any]
    decision:dict[str,Any]
    state_after:dict[str,Any]
    response_directive:dict[str,Any]
    audit:dict[str,Any]
    def to_dict(self):return asdict(self)
