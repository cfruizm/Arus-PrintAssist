from .models import *
from .state import snapshot
from .entity_resolver import EntityResolver
from .decision import DecisionReconciler
from .transitions import TransitionEngine
from .adaptive_controller import AdaptiveCostRouteController
from .contextual_query import ContextualRetrievalQueryBuilder, build_case_detail_acknowledgement

class TurnEngine:
 def __init__(self,interpreter,evidence_engine=None,response_composer=None,resolver=None,route_controller=None,query_builder=None):
  self.interpreter=interpreter;self.evidence_engine=evidence_engine;self.response_composer=response_composer;self.resolver=resolver or EntityResolver();self.reconciler=DecisionReconciler();self.transitions=TransitionEngine();self.route_controller=route_controller or AdaptiveCostRouteController();self.query_builder=query_builder or ContextualRetrievalQueryBuilder()
 def process_turn(self,message,state):
  before=snapshot(state);p=self.interpreter.interpret(message,state);entities=self.resolver.resolve(message,p.entities);d=self.reconciler.reconcile(p,state,entities);state.turn_number+=1
  audit=self.transitions.apply(state,d,increment_turn=False) if d.state_mutation_allowed else {"applied":["turn_increment"],"skipped":["domain_read_only"]}
  if d.state_mutation_allowed:audit["applied"].insert(0,"turn_increment")
  ev={};ans={};query_trace={};metrics={"retrieval_calls":0,"judge_calls":0,"answer_llm_calls":0,"expansion_calls":0,"calls_avoided":0,"route_plans":[]}
  plan=self.route_controller.plan_before_retrieval(d,state);metrics["route_plans"].append(plan.to_dict());metrics["calls_avoided"]+=plan.estimated_calls_avoided
  if d.action=="record_case_detail":
   ans={"mode":"deterministic_case_detail_acknowledgement","text":build_case_detail_acknowledgement(state,d.facts),"citations":[],"knowledge_used":False}
  elif plan.deterministic_response is not None:
   ans={"mode":plan.route,"text":plan.deterministic_response,"citations":[],"knowledge_used":False}
  elif plan.run_retrieval and self.evidence_engine:
   built=self.query_builder.build(message,d,state);query_trace=built.to_dict();ev=self.evidence_engine.evaluate(built.contextual_query,d,state,plan.initial_candidates);metrics["retrieval_calls"]+=1;metrics["judge_calls"]+=1
   after=self.route_controller.plan_after_judgment(d,ev,state);metrics["route_plans"].append(after.to_dict());metrics["calls_avoided"]+=after.estimated_calls_avoided
   if after.allow_expansion and after.expansion_reason:
    expansion=self.route_controller.expansion_query(built.contextual_query,d,state,ev);query_trace["expansion_query"]=expansion;second=self.evidence_engine.evaluate(expansion,d,state,getattr(self.route_controller,"max_candidates",6)-plan.initial_candidates);metrics["retrieval_calls"]+=1;metrics["judge_calls"]+=1;metrics["expansion_calls"]+=1;ev=self.evidence_engine.merge_passes(ev,second);after=self.route_controller.plan_after_expansion(d,ev,state);metrics["route_plans"].append(after.to_dict());metrics["calls_avoided"]+=after.estimated_calls_avoided
   if after.deterministic_response is not None:ans={"mode":after.route,"text":after.deterministic_response,"citations":[],"knowledge_used":False}
   elif after.run_answer_llm and self.response_composer:ans=self.response_composer.compose(built.contextual_query,d,state,ev);metrics["answer_llm_calls"]+=1
  directive={"action":d.action,"intent":d.intent,"requires_retrieval":d.requires_retrieval,"citable_source_ids":[x["id"] for x in ev.get("citable",[])],"adaptive_route":metrics["route_plans"][-1]["route"] if metrics["route_plans"] else None}
  result=TurnResult(message,before,p.__dict__,d.to_dict(),snapshot(state),directive,audit,ev,ans);data=result.to_dict();data["cost_route_metrics"]=metrics;data["interpreter_fallback_used"]=str(p.reasoning_summary).startswith("fallback:");data["retrieval_query_trace"]=query_trace;return _TurnResultProxy(data)
class _TurnResultProxy:
 def __init__(self,data):self.data=data
 def to_dict(self):return self.data
