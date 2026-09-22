from app.agent_core_v2_clean.response_planner import build_response_plan,apply_plan
from app.agent_core_v2_clean.entity_scope import normalize_scope

def ev(i):return {'id':i,'text':'x','page':'1','metadata':{}}
def test_smoke_failure_is_prevented_by_clearing_example_evidence():
 r={'generation_evidence':[ev('R4')],'procedural_scope_guard':{'restricted_to_example':True}}
 u={'intent':'procedural','current_goal':'download driver','goal_updates':{'operation':'download_driver','subject':'printer'}}
 p=build_response_plan('download',u,r,{'status':'partial'});out=apply_plan(r,p)
 assert p.response_plan['mode']=='general_guidance_with_example';assert out['generation_evidence']==[] and out['_answer_context']=={}
def test_brand_alias_is_canonical():assert normalize_scope({'brand':'HP'}).manufacturer=='HP'
def test_documented_ids_are_stable_after_plan():
 p=build_response_plan('x',{'intent':'requirements','current_goal':'requirements'},{'generation_evidence':[ev('R4')]},{'status':'sufficient'});assert p.evidence_plan['documented_ids']==['R1'] and p.evidence_plan['citation_map']['R4']=='R1'
