from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

ALLOWED_ROUTES={"social","capabilities","support_intake","case_update","clarification","technical_query","technical_follow_up","explicit_source","escalation","out_of_scope"}
ALLOWED_INTENTS={"social","conceptual","procedural","troubleshooting","requirements","warranty","architecture","escalation","unknown"}
ALLOWED_UPDATE_TYPES={"product","process","symptom","attempted_action","attempt_result","affected_scope","error_message","evidence","technical_context","resolution_status"}
ALLOWED_NEXT_ACTIONS={"respond_deterministically","update_case","ask_clarification","retrieve","escalate","legacy_fallback"}

@dataclass
class SemanticCaseUpdate:
    type: str
    value: str
    confidence: float
    source: str="current_user_message"

@dataclass
class RetrievalRequest:
    intent: str
    products: list[str]=field(default_factory=list)
    processes: list[str]=field(default_factory=list)
    problem_statement: str|None=None
    question: str|None=None
    exclude_actions: list[str]=field(default_factory=list)

@dataclass
class SemanticDecision:
    route: str
    intent: str
    confidence: float
    next_action: str
    requires_retrieval: bool=False
    requires_clarification: bool=False
    requires_escalation: bool=False
    topic_shift: bool=False
    case_updates: list[SemanticCaseUpdate]=field(default_factory=list)
    missing_information: list[str]=field(default_factory=list)
    clarification_question: str|None=None
    retrieval_request: RetrievalRequest|None=None
    reasoning_summary: str=""

    def to_dict(self)->dict[str,Any]: return asdict(self)
