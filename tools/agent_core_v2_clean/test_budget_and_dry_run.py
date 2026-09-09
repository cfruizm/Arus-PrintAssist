from app.agent_core_v2_clean.budget import BudgetPolicy
from app.agent_core_v2_clean.models import ConversationMemory,TurnUnderstanding
from app.agent_core_v2_clean.memory import apply_understanding
from app.agent_core_v2_clean.dry_run import DryRunUnderstanding,DryRunResponse
from app.agent_core_v2_clean.agent import CleanConversationalAgent
from app.agent_core_v2_clean.policy import ConversationPolicy
def U(**kw):
 d=dict(user_act='new_request',intent='procedural',topic_relation='independent',domain_relevance='in_scope',current_goal='new printing goal',goal_complete=False,goal_updates={},case_updates=[],needs_clarification=False,clarification_target=None,should_retrieve=True,confidence=.9,reasoning_summary='test',degraded=False);d.update(kw);return TurnUnderstanding(**d)
def test_budget_blocks_before_limit():
 ok,reason=BudgetPolicy(max_session_tokens=1000,reserve_tokens=200).can_call({'calls':1,'total_tokens':700,'last_rate_limit':None},estimated_tokens=200)
 assert not ok and reason=='session_token_budget'
def test_rate_limit_blocks_future_calls():assert BudgetPolicy().can_call({'calls':1,'total_tokens':1,'last_rate_limit':{}},100)[0] is False
def test_degraded_does_not_mutate_topic():
 m=ConversationMemory(active_topic='printing case');m.pending_goal.summary='printing case';apply_understanding(m,U(degraded=True,domain_relevance='uncertain',current_goal='untrusted'))
 assert m.active_topic=='printing case'
def test_independent_in_scope_becomes_new_topic():
 m=ConversationMemory(active_topic='old');m.pending_goal.summary='old';apply_understanding(m,U())
 assert m.active_topic=='new printing goal' and m.topic_history[0]['topic']=='old'
def test_dry_run_uses_no_provider():
 a=CleanConversationalAgent(DryRunUnderstanding([U().to_dict()]),ConversationPolicy(),DryRunResponse())
 r=a.process('synthetic turn',ConversationMemory())
 assert r['provider_trace']['understanding']['skipped'] is True and r['answer']['mode']=='dry_run'
