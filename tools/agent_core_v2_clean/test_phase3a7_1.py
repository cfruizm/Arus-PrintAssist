import importlib.util,pathlib,sys,types
R=pathlib.Path(__file__).resolve().parents[2]/"app"/"agent_core_v2_clean";p=types.ModuleType("app.agent_core_v2_clean");p.__path__=[str(R)];sys.modules.setdefault("app",types.ModuleType("app"));sys.modules["app"].__path__=[str(R.parent)];sys.modules["app.agent_core_v2_clean"]=p
def L(n):
 x=importlib.util.spec_from_file_location(f"app.agent_core_v2_clean.{n}",R/f"{n}.py");y=importlib.util.module_from_spec(x);sys.modules[x.name]=y;x.loader.exec_module(y);return y
P=L("answer_context_policy");S=L("semantic_fit")
def test_contract(): assert P.enrich_internal_payload({}, {}, {"goal_updates":{"platform":"X"}})["scope_contract"]["evidence_is_not_user_confirmation"]
def test_question(): assert S.capture_answer_context({"answer":{"text":"Intro. Extra. ¿Which mode?"},"understanding":{}})["closing_question"]=="¿Which mode?"
def test_unanswered_choice(): assert P.enrich_internal_payload({}, {"closing_question":"¿Which mode?"},{"user_act":"follow_up"})["scope_contract"]["previous_choice_request_unanswered"]
