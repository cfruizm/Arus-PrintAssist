from __future__ import annotations
from copy import deepcopy
from .models import ConversationMemory
from .understanding import ConversationUnderstanding
from .reconciler import TurnReconciler
from .memory import apply_understanding
from .retrieval import RetrievalQueryBuilder, ReadOnlyRetrieval
from .evidence import evidence_summary
from .response import ResponseComposer

class CleanConversationalAgent:
    def __init__(self,gateway,budget):
        self.understanding=ConversationUnderstanding(gateway,budget.understanding_max_tokens)
        self.reconciler=TurnReconciler()
        self.response=ResponseComposer(gateway,budget.response_max_tokens)
    def process(self,message,memory):
        before=deepcopy(memory.to_dict())
        u=self.understanding.interpret(message,memory)
        u,warnings=self.reconciler.reconcile(u,memory,message)
        decision=self.reconciler.decision(u,memory)
        apply_understanding(memory,u)
        retrieval={"enabled":False,"ok":False,"evidence":[],"count":0,"llm_called":False,"production_state_changed":False}
        if decision["action"]=="retrieve":
            builder=RetrievalQueryBuilder();q=builder.build(message,memory,u);current=builder.current_only(message,u)
            retrieval=ReadOnlyRetrieval().search(q,current)
            assessment=evidence_summary(message,u,retrieval.get("evidence") or [])
            retrieval.update({"selected":assessment["selected"],"coverage":assessment["coverage"],"sufficient":assessment["sufficient"]})
        answer=self.response.compose(message,memory,u,decision,retrieval)
        if answer.mode in {"grounded_answer","guardrail_replaced"} and u.intent in {"conceptual","requirements"} and u.goal_complete:
            memory.pending_goal.status="complete"
        if u.goal_complete and u.intent=="troubleshooting":memory.support_case.resolution_status="resolved";memory.support_case.status="resolved"
        if answer.text.endswith("?"):memory.last_assistant_question=answer.text.split("\n")[-1].strip()
        else:memory.last_assistant_question=None
        return {"input":message,"state_before":before,"understanding":u.to_dict(),"understanding_contract":{"valid":self.understanding.contract_valid,"error":self.understanding.validation_error},"goal_update_normalization":self.understanding.normalization,"decision":decision,"answer":answer.to_dict(),"retrieval":retrieval,"warnings":warnings,"state_after":deepcopy(memory.to_dict()),"production_changed":False,"provider_trace":{"understanding":self.understanding.last_provider_result,"response":self.response.last_provider_result}}
