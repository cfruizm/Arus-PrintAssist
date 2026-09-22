import importlib.util,pathlib,sys,types
ROOT=pathlib.Path(__file__).resolve().parents[2]/"app"/"agent_core_v2_clean"
pkg=types.ModuleType("app.agent_core_v2_clean");pkg.__path__=[str(ROOT)];sys.modules.setdefault("app",types.ModuleType("app"));sys.modules["app"].__path__=[str(ROOT.parent)];sys.modules["app.agent_core_v2_clean"]=pkg
models=types.ModuleType("app.agent_core_v2_clean.models")
class AgentResponse:
 def __init__(self,*a,**k):pass
models.AgentResponse=AgentResponse;sys.modules[models.__name__]=models
def load(n):
 spec=importlib.util.spec_from_file_location(f"app.agent_core_v2_clean.{n}",ROOT/f"{n}.py");m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
policy=load("answer_context_policy");internal=load("internal_knowledge")

def test_followup_marks_unanswered_previous_choice():
 out=policy.enrich_internal_payload({}, {"goal":"configure","closing_question":"Which deployment mode?"},{"user_act":"follow_up","goal_updates":{"platform":"Example"}});c=out["scope_contract"];assert c["previous_choice_request_unanswered"] is True;assert c["confirmed_facts"][0]["value"]=="Example"
def test_answer_to_question_does_not_mark_choice_unanswered():
 out=policy.enrich_internal_payload({}, {"closing_question":"Which mode?"},{"user_act":"answer_to_question","goal_updates":{"mode":"local"}});assert out["scope_contract"]["previous_choice_request_unanswered"] is False
def test_no_product_specific_branching():
 import inspect
 text=inspect.getsource(policy)+inspect.getsource(internal)
 for forbidden in ("PaperCut","HP SDS","card_reader","Cloud DCA"):
  assert forbidden not in text
