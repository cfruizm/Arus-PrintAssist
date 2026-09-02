from __future__ import annotations
from .models import ConversationState,TurnResult
from .state import snapshot
from .entity_resolver import EntityResolver
from .decision_reconciler import DecisionReconciler
from .transition_engine import TransitionEngine

class TurnEngine:
    def __init__(self,interpreter,entity_resolver=None):
        self.interpreter=interpreter;self.entity_resolver=entity_resolver or EntityResolver();self.reconciler=DecisionReconciler();self.transitions=TransitionEngine()
    def process_turn(self,message,state:ConversationState):
        before=snapshot(state);proposal=self.interpreter.interpret(message,state);entities=self.entity_resolver.resolve(message,proposal.entities);decision=self.reconciler.reconcile(message,proposal,state,entities);audit=self.transitions.apply(state,decision) if decision.state_mutation_allowed else {"applied":[],"skipped":["read_only_decision"]};directive=self._directive(decision,state)
        return TurnResult(message,before,proposal.__dict__,decision.to_dict(),snapshot(state),directive,audit)
    @staticmethod
    def _directive(decision,state):
        return {"action":decision.action,"intent":decision.intent,"requires_retrieval":decision.requires_retrieval,"clarification_question":decision.clarification_question,"active_product_ids":[x.canonical_id for x in state.active_topic.products],"escalation_status":state.escalation.status}
