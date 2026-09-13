from app.agent_core_v2_clean.topic_boundary import infer_topic_boundary
from app.agent_core_v2_clean.answer_grounding_guard import unsafe_global_absence_claim

def test_introduced_material_scope_is_changed_scope():
 before={'pending_goal':{'summary':'consultar dato','known_details':{'operation':'consultar dato','subject':'dato'}}}
 now={'topic_relation':'same_topic','current_goal':'consultar dato en otra plataforma','goal_updates':{'operation':'consultar dato','subject':'dato','platform':'otra'}}
 b=infer_topic_boundary(before,now)
 assert b.relation=='same_topic_changed_scope'
 assert b.previous_evidence_role=='comparison_only'

def test_explicit_new_topic_is_preserved():
 before={'pending_goal':{'summary':'consultar dato','known_details':{'operation':'consultar','subject':'dato','platform':'otra'}}}
 now={'topic_relation':'new_topic','current_goal':'actualizar componente','goal_updates':{'operation':'actualizar','subject':'componente'}}
 assert infer_topic_boundary(before,now).relation=='new_topic'

def test_global_absence_claim_rejected_when_current_candidates_exist():
 retrieval={'diagnostic_evidence':[{'id':'R1','text':'contenido actual'}]}
 assert unsafe_global_absence_claim('La documentación no contiene información',retrieval)
