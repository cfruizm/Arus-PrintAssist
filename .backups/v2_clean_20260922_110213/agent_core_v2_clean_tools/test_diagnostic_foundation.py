from app.agent_core_v2_clean.models import ConversationMemory,TurnUnderstanding
from app.agent_core_v2_clean.memory import apply_understanding
from app.agent_core_v2_clean.policy import ConversationPolicy
from app.agent_core_v2_clean.telemetry import empty,add_result,turn_metrics
def U(**kw):
 d=dict(user_act='new_request',intent='procedural',topic_relation='same_topic',domain_relevance='in_scope',current_goal='configure access',goal_complete=False,goal_updates={},case_updates=[],needs_clarification=False,clarification_target=None,should_retrieve=True,confidence=.9,reasoning_summary='semantic',degraded=False);d.update(kw);return TurnUnderstanding(**d)
def test_retrieval_request_is_deferred_without_inventing():assert ConversationPolicy().decide(U(),ConversationMemory()).action=='defer_to_retrieval'
def test_out_of_scope_new_topic_does_not_clear_active_goal():
 m=ConversationMemory(active_topic='existing');m.pending_goal.summary='existing goal';apply_understanding(m,U(topic_relation='new_topic',domain_relevance='out_of_scope',current_goal='external'))
 assert m.active_topic=='existing' and m.pending_goal.summary=='existing goal'
def test_degraded_turn_preserves_intent_and_context():
 m=ConversationMemory(active_topic='case');m.pending_goal.summary='solve case';m.pending_goal.intent='troubleshooting';apply_understanding(m,U(intent='troubleshooting',current_goal='solve case',goal_updates={'latest_user_reply':'fixed ip'},degraded=True))
 assert m.pending_goal.intent=='troubleshooting' and 'latest_user_reply' not in m.pending_goal.known_details
def test_telemetry_counts_both_calls():
 t=empty();a={'ok':True,'purpose':'understanding','usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15},'latency_ms':12};b={'ok':False,'purpose':'response','usage':{},'latency_ms':3,'error_code':'rate_limited','error_message':'limit','metadata':{}}
 add_result(t,a);add_result(t,b);m=turn_metrics(a,b)
 assert t['calls']==2 and t['failed_calls']==1 and t['total_tokens']==15 and m['calls']==2
