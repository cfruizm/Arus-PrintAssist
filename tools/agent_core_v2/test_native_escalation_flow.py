from app.agent_core_v2.models import ConversationState, InterpreterProposal
from app.agent_core_v2.decision import DecisionReconciler
from app.agent_core_v2.transitions import TransitionEngine
from app.agent_core_v2.response import ResponseComposer

def proposal(act, intent, action, facts=None):
    return InterpreterProposal(act,intent,action,"same_topic",[],facts or [],None,.9,"test")

def test_native_escalation_progresses_without_retrieval_or_product_rules():
    state=ConversationState(); reconciler=DecisionReconciler(); transitions=TransitionEngine(); composer=ResponseComposer(None)
    turns=[
      ("Solicitar escalamiento",proposal("escalation","escalation","start_escalation"),"issue_description"),
      ("La operación falla con un mensaje de conexión",proposal("technical_request","troubleshooting","retrieve",[{"type":"symptom","value":"la operación falla"},{"type":"error_message","value":"mensaje de conexión"}]),"impact_scope"),
      ("Afecta a varios usuarios",proposal("clarification","unknown","ask_clarification",[{"type":"affected_scope","value":"varios usuarios"}]),"troubleshooting_performed"),
      ("Se validó conectividad y sigue igual",proposal("attempt_result","troubleshooting","record_attempt_result",[{"type":"attempted_action","value":"validación de conectividad"},{"type":"attempt_result","value":"sigue igual"}]),None),
    ]
    for message,raw,expected_pending in turns:
        decision=reconciler.reconcile(raw,state,[]); setattr(decision,"current_message",message)
        transitions.apply(state,decision); answer=composer.compose_conversation(message,decision,state)
        assert decision.requires_retrieval is False
        assert state.escalation.pending_field==expected_pending
        assert answer["mode"]=="native_escalation"
    assert state.escalation.status=="ready"
    assert set(state.escalation.collected_fields)=={"issue_description","impact_scope","troubleshooting_performed"}

def test_cancel_remains_available_during_escalation():
    state=ConversationState(); state.escalation.status="collecting"
    raw=proposal("cancel","cancel","cancel_all")
    decision=DecisionReconciler().reconcile(raw,state,[])
    assert decision.action=="cancel_all"
