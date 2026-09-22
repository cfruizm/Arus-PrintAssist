import json
from types import SimpleNamespace
from app.agent_core_v2_clean.models import ConversationMemory
from app.agent_core_v2_clean.understanding import ConversationUnderstanding
from app.agent_core_v2_clean.reconciler import TurnReconciler
from app.agent_core_v2_clean.memory import apply_understanding

def U(**kw):
    d=dict(user_act="new_request",intent="troubleshooting",topic_relation="same_topic",domain_relevance="in_scope",current_goal="resolver falla de impresión",goal_complete=False,goal_updates={},case_updates=[{"type":"symptom","value":"No imprime"}],needs_clarification=True,clarification_target="modelo exacto",should_retrieve=True,confidence=.9,reasoning_summary="x",degraded=False);d.update(kw);from app.agent_core_v2_clean.models import TurnUnderstanding;return TurnUnderstanding(**d)

def test_active_case_does_not_get_blocked_by_clarification():
    m=ConversationMemory();m.active_topic="PaperCut";m.pending_goal.summary="resolver falla";m.pending_goal.intent="troubleshooting";m.support_case.status="diagnosing"
    u=U(user_act="follow_up")
    u,_=TurnReconciler().reconcile(u,m)
    d=TurnReconciler().decision(u,m)
    assert d["action"]=="retrieve" and not u.needs_clarification

def test_clear_conceptual_never_clarifies():
    m=ConversationMemory();u=U(intent="conceptual",user_act="new_request",current_goal="explicar que es PaperCut Hive",needs_clarification=True,clarification_target="version")
    u,_=TurnReconciler().reconcile(u,m)
    assert not u.needs_clarification and TurnReconciler().decision(u,m)["action"]=="retrieve"

def test_new_topic_does_not_mix_old_case():
    m=ConversationMemory(active_topic="PaperCut",support_case=__import__('app.agent_core_v2_clean.models',fromlist=['SupportCase']).SupportCase(status='diagnosing',symptoms=['error']))
    u=U(intent="conceptual",topic_relation="new_topic",current_goal="explicar otra herramienta",case_updates=[],needs_clarification=False)
    apply_understanding(m,u)
    assert m.active_topic=="explicar otra herramienta" and m.support_case.status=="idle" and m.case_history

def test_no_v2_dependency():
    import pathlib
    root=pathlib.Path('app/agent_core_v2_clean')
    text='\n'.join(p.read_text(encoding='utf-8') for p in root.glob('*.py'))
    assert 'app.agent_core_v2.' not in text
