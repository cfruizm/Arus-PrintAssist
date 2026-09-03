from .models import *
from .state import snapshot
from .entity_resolver import EntityResolver
from .decision import DecisionReconciler
from .transitions import TransitionEngine
class TurnEngine:
 def __init__(self,interpreter,evidence_engine=None,response_composer=None,resolver=None):self.interpreter=interpreter;self.evidence_engine=evidence_engine;self.response_composer=response_composer;self.resolver=resolver or EntityResolver();self.reconciler=DecisionReconciler();self.transitions=TransitionEngine()
 def process_turn(self,message,state):
  before=snapshot(state);p=self.interpreter.interpret(message,state);entities=self.resolver.resolve(message,p.entities);d=self.reconciler.reconcile(p,state,entities);audit=self.transitions.apply(state,d) if d.state_mutation_allowed else {"applied":[],"skipped":["read_only"]};ev={};ans={}
  if d.requires_retrieval and self.evidence_engine:
   compat=getattr(self.evidence_engine,"compatibility",None)
   if compat is not None and getattr(compat,"registry",None) is None:compat.registry=getattr(self.resolver,"registry",None)
   ev=self.evidence_engine.evaluate(message,d,state)
   if self.response_composer:ans=self.response_composer.compose(message,d,state,ev)
  directive={"action":d.action,"intent":d.intent,"requires_retrieval":d.requires_retrieval,"citable_source_ids":[x["id"] for x in ev.get("citable",[])]}
  return TurnResult(message,before,p.__dict__,d.to_dict(),snapshot(state),directive,audit,ev,ans)
