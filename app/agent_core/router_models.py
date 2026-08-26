from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ContextFact:
    fact_type: str
    value: str
    confidence: float = 1.0
    source: str = "current_user_message"
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ConversationState:
    last_route: str | None = None
    last_user_act: str | None = None
    awaiting_clarification: bool = False
    clarification_reason: str | None = None
    clarification_options: list[str] = field(default_factory=list)

@dataclass
class TopicState:
    products: list[str] = field(default_factory=list)
    processes: list[str] = field(default_factory=list)
    subject_terms: list[str] = field(default_factory=list)
    context_facts: list[ContextFact] = field(default_factory=list)

@dataclass
class TechnicalCase:
    status: str = "idle"
    symptoms: list[str] = field(default_factory=list)
    attempted_actions: list[str] = field(default_factory=list)
    failed_actions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    affected_users: str | None = None
    impact: str | None = None
    resolution_status: str | None = None
    context_facts: list[ContextFact] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.status not in {"idle", "resolved", "completed"}

@dataclass
class RouterShadowState:
    conversation: ConversationState = field(default_factory=ConversationState)
    topic: TopicState = field(default_factory=TopicState)
    technical_case: TechnicalCase = field(default_factory=TechnicalCase)
    turn_number: int = 0

@dataclass
class RouteDecision:
    route: str
    reason: str
    confidence: float
    use_retrieval: bool = False
    use_llm: bool = False
    inherit_context: bool = False
    needs_clarification: bool = False
    detected_products: list[str] = field(default_factory=list)
    detected_processes: list[str] = field(default_factory=list)
    case_updates: list[ContextFact] = field(default_factory=list)
    deterministic_response: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
