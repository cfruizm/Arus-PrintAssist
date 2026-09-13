from __future__ import annotations
from .topic_boundary import infer_topic_boundary

def reconcile_turn(understanding, memory, message):
    corrections=[]
    before = memory.to_dict() if hasattr(memory, "to_dict") else {}
    payload = understanding.to_dict() if hasattr(understanding, "to_dict") else dict(understanding or {})
    boundary = infer_topic_boundary(before, payload)
    has_anchor=bool(getattr(memory,'active_topic',None) or getattr(memory,'last_assistant_question',None))
    if getattr(understanding,'user_act',None)=='request_elaboration' and not has_anchor:
        understanding.user_act='new_request'; understanding.topic_relation='new_topic'; corrections.append('orphan_elaboration_to_new_request')
    elif boundary.relation == 'new_topic':
        understanding.user_act='new_request'; understanding.topic_relation='new_topic'; corrections.append('independent_goal_preserved_as_new_topic')
    elif boundary.relation == 'same_topic_changed_scope':
        understanding.topic_relation='same_topic'; corrections.append('material_scope_change_detected')
    return understanding, corrections, boundary.to_dict()
