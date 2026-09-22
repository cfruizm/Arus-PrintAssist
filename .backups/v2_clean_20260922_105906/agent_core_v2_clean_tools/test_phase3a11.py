from app.agent_core_v2_clean.entity_scope import normalize_scope
from app.agent_core_v2_clean.citation_registry import register_evidence
from app.agent_core_v2_clean.response_planner import build_response_plan,apply_plan_to_retrieval

def ev(i,product=None):return {"id":i,"text":"evidence text","page":"1","metadata":{"product":product} if product else {}}
def test_scope_aliases_are_canonical():
 s=normalize_scope({"brand":"HP","os":"Windows","printer_model":"X"});assert s.manufacturer=="HP" and s.operating_system=="Windows" and s.model=="X"
def test_citations_are_assigned_once_after_selection():
 a=ev("R8");b=ev("R3");b["text"]="different evidence";rows,m=register_evidence([a,b]);assert [x["id"] for x in rows]==["R1","R2"] and m["R8"]=="R1"
def test_generic_procedure_with_product_example_uses_general_guidance():
 r={"generation_evidence":[ev("R4","platform_x")],"procedural_scope_guard":{"restricted_to_example":True}}
 u={"intent":"procedural","current_goal":"download driver","goal_updates":{"operation":"download","subject":"driver"}}
 p=build_response_plan("How do I download a driver?",u,r,{"status":"partial"});assert p.response_plan["mode"]=="general_guidance_with_example" and p.response_plan["question_target"]=="manufacturer_or_model" and not p.response_plan["allow_documented_claims"]
def test_explicit_brand_is_not_generic():
 u={"intent":"procedural","current_goal":"download driver","goal_updates":{"brand":"HP","operating_system":"Windows"}}
 p=build_response_plan("download",u,{"generation_evidence":[ev("R4")]},{"status":"sufficient"});assert p.request["scope"]["manufacturer"]=="HP" and p.response_plan["mode"]=="documented"
def test_internal_mode_clears_generation_evidence():
 p=build_response_plan("what",{"intent":"conceptual","current_goal":"define queue"},{"generation_evidence":[]},{"status":"insufficient"});out=apply_plan_to_retrieval({"generation_evidence":[ev("OLD")]},p);assert out["generation_evidence"]==[]
