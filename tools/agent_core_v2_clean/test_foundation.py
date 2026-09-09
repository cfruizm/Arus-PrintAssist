from app.agent_core_v2_clean.models import ConversationMemory,TurnUnderstanding
from app.agent_core_v2_clean.memory import apply_understanding
from app.agent_core_v2_clean.policy import ConversationPolicy

def u(**kw):
 base=dict(user_act="new_request",intent="procedural",topic_relation="same_topic",domain_relevance="in_scope",current_goal="configure access for job release",goal_complete=False,goal_updates={},case_updates=[],needs_clarification=True,clarification_target="target scope",should_retrieve=False,confidence=.9,reasoning_summary="semantic")
 base.update(kw);return TurnUnderstanding(**base)
def test_short_answer_enriches_instead_of_replacing_goal():
 m=ConversationMemory();apply_understanding(m,u());apply_understanding(m,u(user_act="answer_to_question",current_goal="configure access for job release for one user",goal_updates={"target_scope":"one user"},needs_clarification=False,clarification_target=None,goal_complete=True))
 assert "job release" in m.pending_goal.summary and m.pending_goal.known_details["target_scope"]=="one user"
def test_failure_creates_case():
 m=ConversationMemory();x=u(intent="troubleshooting",user_act="reported_failure",current_goal="restore operation",case_updates=[{"type":"symptom","value":"operation cannot be completed"}],needs_clarification=True,clarification_target="failure point")
 apply_understanding(m,x);d=ConversationPolicy().decide(x,m)
 assert m.support_case.status=="diagnosing" and d.action=="diagnose"
def test_independent_out_of_scope_preserves_topic():
 m=ConversationMemory(active_topic="printing issue");x=u(user_act="independent_question",intent="unknown",topic_relation="independent",domain_relevance="out_of_scope",current_goal="unrelated question",needs_clarification=False,clarification_target=None)
 apply_understanding(m,x);d=ConversationPolicy().decide(x,m)
 assert m.active_topic=="printing issue" and d.action=="redirect_scope"
def test_no_dependency_on_previous_v2():
 import ast,pathlib
 root=pathlib.Path("app/agent_core_v2_clean")
 for p in root.glob("*.py"):
  tree=ast.parse(p.read_text())
  for n in ast.walk(tree):
   if isinstance(n,(ast.Import,ast.ImportFrom)):
    text=ast.unparse(n)
    assert "app.agent_core_v2." not in text
