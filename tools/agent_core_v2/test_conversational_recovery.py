from app.agent_core_v2.conversation_planner import ConversationPlanner
from app.agent_core_v2.models import ConversationState,CanonicalDecision,EntityRef,InterpreterProposal
from app.agent_core_v2.decision import DecisionReconciler

def d(intent,action='retrieve'):
 return CanonicalDecision(action,intent,'technical_request','same_topic',[],[],None,.9,[],False,action=='retrieve')

def test_failure_gets_diagnostic_plan():
 p=ConversationPlanner().build(d('troubleshooting'),ConversationState(),{})
 assert p.strategy=='diagnose' and p.ask_one_question

def test_missing_procedure_gets_clarify_then_guide():
 p=ConversationPlanner().build(d('procedural'),ConversationState(),{})
 assert p.strategy=='clarify_then_guide' and p.allow_general_knowledge

def test_same_topic_new_entity_can_be_saved():
 s=ConversationState();e=EntityRef('process','generic_process','Proceso')
 raw=InterpreterProposal('technical_request','procedural','retrieve','same_topic',[],[],None,.9,'semantic')
 assert DecisionReconciler().reconcile(raw,s,[e]).state_mutation_allowed
