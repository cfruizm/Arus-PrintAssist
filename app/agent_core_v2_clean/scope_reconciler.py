from .topic_boundary import infer_topic_boundary
def reconcile_turn(u,memory,message):
 corrections=[];boundary=infer_topic_boundary(memory.to_dict(),u.to_dict());case_active=memory.support_case.status in {"diagnosing","reopened"}
 if case_active and u.intent in {"troubleshooting","procedural","requirements","verification"} and u.domain_relevance=="in_scope":u.topic_relation="same_topic";boundary=type(boundary)("same_topic_refinement","active_case_continuity",boundary.shared_ratio,boundary.changed_dimensions,boundary.introduced_dimensions,"primary");corrections.append("active_case_continuity_preserved")
 elif boundary.relation=="new_topic":u.user_act="new_request";u.topic_relation="new_topic";corrections.append("independent_goal_preserved_as_new_topic")
 elif boundary.relation=="same_topic_changed_scope":u.topic_relation="same_topic";corrections.append("material_scope_change_detected")
 return u,corrections,boundary.to_dict()
