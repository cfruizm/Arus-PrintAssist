import importlib.util
import pathlib
import sys
import types

ROOT=pathlib.Path(__file__).resolve().parents[2]/"app"/"agent_core_v2_clean"
pkg=types.ModuleType("app.agent_core_v2_clean");pkg.__path__=[str(ROOT)]
sys.modules.setdefault("app",types.ModuleType("app"));sys.modules["app"].__path__=[str(ROOT.parent)]
sys.modules["app.agent_core_v2_clean"]=pkg
models=types.ModuleType("app.agent_core_v2_clean.models")
class AgentResponse:
 def __init__(self,*args,**kwargs):pass
models.AgentResponse=AgentResponse
sys.modules[models.__name__]=models

def load(name):
 spec=importlib.util.spec_from_file_location(f"app.agent_core_v2_clean.{name}",ROOT/f"{name}.py");mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod);return mod
policy=load("answer_context_policy");internal=load("internal_knowledge")

def test_authorized_evidence_is_compact_and_deduplicated():
 shared={"source":"same","page":"1","text":"validate configuration safely"};retrieval={"generation_evidence":[shared],"_answer_context":{"cited_evidence":[shared,{"source":"prior","page":"2","text":"validate directory fields before rollout"}]}};result=internal.authorized_evidence(retrieval,"what should I validate","configure safely");assert len(result)==2;assert len({x["stable_id"] for x in result})==2;assert all(len(x["text"])<=900 for x in result)
def test_previous_context_does_not_duplicate_cited_evidence():
 result=policy.enrich_internal_payload({}, {"goal":"configure","main_text_excerpt":"x"*1000,"cited_evidence":[{"text":"large"}]},{"user_act":"follow_up"});ctx=result["previous_answer_context"];assert "cited_evidence" not in ctx and "cited_ids" not in ctx and len(ctx["main_text_excerpt"])==420
def test_limits_preserve_output_budget():
 composer=internal.ControlledInternalKnowledgeComposer(None,520);assert composer.max_tokens==520
