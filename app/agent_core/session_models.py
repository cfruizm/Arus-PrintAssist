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
class AttemptedAction:
    description: str
    result: str | None = None
    evidence: list[str] = field(default_factory=list)

@dataclass
class ConversationState:
    last_route: str | None = None
    last_user_act: str | None = None
    awaiting_clarification: bool = False
    clarification_type: str | None = None
    clarification_options: list[str] = field(default_factory=list)

@dataclass
class TopicState:
    products: list[str] = field(default_factory=list)
    processes: list[str] = field(default_factory=list)
    subject_terms: list[str] = field(default_factory=list)
    intent: str | None = None
    explicit_source_url: str | None = None
    context_facts: list[ContextFact] = field(default_factory=list)

@dataclass
class TechnicalCase:
    status: str = "idle"
    symptoms: list[str] = field(default_factory=list)
    affected_assets: list[str] = field(default_factory=list)
    affected_users: str | None = None
    impact: str | None = None
    attempted_actions: list[AttemptedAction] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    context_facts: list[ContextFact] = field(default_factory=list)
    resolution_status: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status not in {"idle", "resolved", "completed"}

@dataclass
class AgentCoreSession:
    conversation: ConversationState = field(default_factory=ConversationState)
    topic: TopicState = field(default_factory=TopicState)
    technical_case: TechnicalCase = field(default_factory=TechnicalCase)
