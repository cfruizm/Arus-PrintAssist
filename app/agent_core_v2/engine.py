from .models import *
from .state import snapshot
from .entity_resolver import EntityResolver
from .decision import DecisionReconciler
from .transitions import TransitionEngine
from .adaptive_controller import AdaptiveCostRouteController
from .contextual_query import ContextualRetrievalQueryBuilder,build_case_detail_acknowledgement
class TurnEngine:
 def __init__(self,interpreter,evidence_engine=None,response_composer=None,resolver=None,route_controller=None,query_builder=None):self.interpreter=interpreter;self.evidence_engine=evidence_engine;self.response_composer=response_composer;self.resolver=resolver or EntityResolver();self.reconciler=DecisionReconciler();self.transitions=TransitionEngine();self.route_controller=route_controller or AdaptiveCostRouteController();self.query_builder=query_builder or ContextualRetrievalQueryBuilder()
 def process_turn(self,message,state):
  before=snapshot(state);p=self.interpreter.interpret(message,state);trace=dict(getattr(self.interpreter,"last_trace",{}) or {});entities=self.resolver.resolve(message,p.entities);d=self.reconciler.reconcile(p,state,entities);state.turn_number+=1;audit=self.transitions.apply(state,d,increment_turn=False) if d.state_mutation_allowed else {"applied":["turn_increment"],"skipped":["read_only_or_lateral"]}
  if d.state_mutation_allowed:audit["applied"].insert(0,"turn_increment")
  ev={};ans={};qtrace={};metrics={"retrieval_calls":0,"judge_calls":0,"answer_llm_calls":0,"expansion_calls":0,"calls_avoided":0,"route_plans":[]};plan=self.route_controller.plan_before_retrieval(d,state);metrics["route_plans"].append(plan.to_dict());metrics["calls_avoided"]+=plan.estimated_calls_avoided
  if plan.route in {"compose_lateral","compose_escalation","compose_cancel","compose_clarification"} and self.response_composer:
   ans=self.response_composer.compose_conversation(message,d,state);metrics["answer_llm_calls"]+=1
  elif d.action=="record_case_detail":ans={"mode":"deterministic_case_detail_acknowledgement","text":build_case_detail_acknowledgement(state,d.facts),"citations":[],"knowledge_used":False}
  elif d.action=="record_attempt":ans={"mode":"deterministic_attempt_acknowledgement","text":"Registré la validación realizada. ¿Qué resultado obtuviste?","citations":[],"knowledge_used":False}
  elif d.action=="record_attempt_result":ans={"mode":"deterministic_attempt_result_acknowledgement","text":"Registré el resultado y evitaré recomendar nuevamente una acción que no resolvió el caso.","citations":[],"knowledge_used":False}
  elif plan.run_retrieval and self.evidence_engine:
   built=self.query_builder.build(message,d,state);qtrace=built.to_dict();ev=self.evidence_engine.evaluate(built.contextual_query,d,state,plan.initial_candidates);metrics["retrieval_calls"]+=1;metrics["judge_calls"]+=0 if (ev.get("judge") or {}).get("skipped") else 1;after=self.route_controller.plan_after_judgment(d,ev,state);metrics["route_plans"].append(after.to_dict())
   if after.run_answer_llm and self.response_composer:ans=self.response_composer.compose(built.contextual_query,d,state,ev);metrics["answer_llm_calls"]+=1
  directive={"action":d.action,"intent":d.intent,"requires_retrieval":d.requires_retrieval,"citable_source_ids":[x["id"] for x in ev.get("citable",[])],"adaptive_route":metrics["route_plans"][-1]["route"] if metrics["route_plans"] else None};result=TurnResult(message,before,p.__dict__,d.to_dict(),snapshot(state),directive,audit,ev,ans);data=result.to_dict();data["cost_route_metrics"]=metrics;data["semantic_interpretation_trace"]=trace;data["retrieval_query_trace"]=qtrace;return _Proxy(data)
class _Proxy:
 def __init__(self,data):self.data=data
 def to_dict(self):return self.data
