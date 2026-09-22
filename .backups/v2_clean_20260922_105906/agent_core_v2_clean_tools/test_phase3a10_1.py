from app.agent_core_v2_clean.topic_boundary import infer_topic_boundary
from app.agent_core_v2_clean.procedural_recovery import should_compact_retry

def test_independent_goal_is_new_topic():
 before={'pending_goal':{'summary':'consultar credencial','known_details':{'operation':'consultar','subject':'credencial'}}}
 now={'topic_relation':'same_topic','current_goal':'actualizar software de dispositivo','goal_updates':{'operation':'actualizar','subject':'software'}}
 assert infer_topic_boundary(before,now).relation=='new_topic'
def test_changed_scope_demotes_previous_evidence():
 before={'pending_goal':{'summary':'consultar dato en plataforma','known_details':{'operation':'consultar','subject':'dato','platform':'A'}}}
 now={'topic_relation':'same_topic','current_goal':'consultar dato en otra plataforma','goal_updates':{'operation':'consultar','subject':'dato','platform':'B'}}
 assert infer_topic_boundary(before,now).previous_evidence_role=='comparison_only'
def test_length_requires_compact_retry():
 assert should_compact_retry({'finish_reason':'length'})
