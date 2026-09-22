from app.agent_core_v2_clean.entity_scope import normalize_scope
from app.agent_core_v2_clean.state_scope import enrich_understanding
from app.agent_core_v2_clean.response_planner import build_response_plan

def test_platform_that_looks_like_os_is_not_product():
 s=normalize_scope({'subject':'impresora HP E52645','platform':'Windows 11 64 bits'})
 assert s.model.upper()=='E52645' and s.manufacturer.upper()=='HP'
 assert s.operating_system.lower()=='windows 11' and s.architecture=='64 bits' and s.product is None
def test_followup_merges_state_and_delta():
 r={'state_after':{'pending_goal':{'known_details':{'subject':'impresora HP E52645','platform':'Windows 11 64 bits'}}},'understanding':{'intent':'procedural','goal_updates':{'operation':'instalar_driver','driver_type':'punto_a_punto'}}}
 enrich_understanding(r);d=r['understanding']['goal_updates'];assert d['subject']=='impresora HP E52645' and d['operation']=='instalar_driver'
def test_plan_no_longer_asks_for_known_os_or_model():
 u={'intent':'procedural','goal_updates':{'operation':'instalar_driver','subject':'impresora HP E52645','platform':'Windows 11 64 bits','driver_type':'punto_a_punto'}}
 p=build_response_plan('x',u,{}, {'status':'insufficient'});assert p.request['missing_material_details']==[]
