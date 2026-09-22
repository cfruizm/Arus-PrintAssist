from __future__ import annotations
from .topic_boundary import infer_topic_boundary

def reconcile_turn(understanding,memory,message):
 corrections=[];before=memory.to_dict() if hasattr(memory,"to_dict") else {};payload=understanding.to_dict();boundary=infer_topic_boundary(before,payload)
 has_anchor=bool(getattr(memory,"active_topic",None) or getattr(memory,"last_assistant_question",None));case=getattr(memory,"support_case",None);case_active=bool(case and case.status in {"diagnosing","reopened"})
 continuation=case_active and understanding.intent in {"troubleshooting","procedural","requirements","verification"} and understanding.domain_relevance=="in_scope"
 if understanding.user_act=="request_elaboration" and not has_anchor:understanding.user_act="new_request";understanding.topic_relation="new_topic";corrections.append("orphan_elaboration_to_new_request")
 elif continuation:
  understanding.topic_relation="same_topic";boundary=type(boundary)("same_topic_refinement","active_case_continuity",boundary.shared_ratio,boundary.changed_dimensions,boundary.introduced_dimensions,"primary");corrections.append("active_case_continuity_preserved")
 elif boundary.relation=="new_topic":understanding.user_act="new_request";understanding.topic_relation="new_topic";corrections.append("independent_goal_preserved_as_new_topic")
 elif boundary.relation=="same_topic_changed_scope":understanding.topic_relation="same_topic";corrections.append("material_scope_change_detected")
 return understanding,corrections,boundary.to_dict()
