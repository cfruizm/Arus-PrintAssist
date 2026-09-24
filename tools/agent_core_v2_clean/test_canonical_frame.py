from app.agent_core_v2_clean.canonical_frame import build_frame,validate_frame

def base_memory(subject=""):
    return {"pending_goal":{"intent":"conceptual","known_details":({"subject":subject} if subject else {})},"support_case":{"symptoms":[],"observations":[],"attempts":[],"affected_scope":None}}

def test_followup_inherits_subject_without_product_rules():
    previous={"subject":{"type":"product","value":"Platform Alpha","canonical_id":"alpha","confidence":1},"topic":{"topic_id":"topic-a"}}
    u={"user_act":"follow_up","intent":"conceptual","topic_relation":"same_topic","current_goal":"What is it used for?","should_retrieve":True}
    f=build_frame("What is it used for?",u,base_memory(),{},previous)
    assert f.subject.value=="Platform Alpha" and f.topic.topic_id=="topic-a" and not validate_frame(f)

def test_operation_does_not_replace_subject():
    previous={"subject":{"type":"component","value":"Component Beta","canonical_id":"beta","confidence":1},"topic":{"topic_id":"topic-b"}}
    u={"user_act":"follow_up","intent":"requirements","topic_relation":"same_topic","current_goal":"Which environments are supported?","should_retrieve":True}
    f=build_frame("Which environments are supported?",u,base_memory(),{},previous)
    assert f.subject.value=="Component Beta"
    assert f.operation.text=="Which environments are supported?"

def test_explicit_subject_starts_independent_frame():
    u={"user_act":"new_request","intent":"procedural","topic_relation":"new_topic","current_goal":"How do I perform the operation?","goal_updates":{"product":"Platform Gamma"},"should_retrieve":True}
    f=build_frame("How do I perform the operation?",u,base_memory(),{},None)
    assert f.subject.value=="Platform Gamma" and f.subject.origin=="user_confirmed"

def test_unresolved_followup_fails_invariant():
    u={"user_act":"follow_up","intent":"conceptual","topic_relation":"same_topic","current_goal":"And why?","should_retrieve":True}
    f=build_frame("And why?",u,base_memory(),{},None)
    assert "follow_up_requires_subject" in validate_frame(f)

def test_case_is_preserved_independently():
    memory=base_memory("Service Delta");memory["support_case"]={"symptoms":["stops reporting"],"observations":[],"attempts":[],"affected_scope":"multiple devices","resolution_status":None}
    u={"user_act":"new_request","intent":"troubleshooting","topic_relation":"new_topic","current_goal":"diagnose reporting","goal_updates":{"subject":"Service Delta"},"should_retrieve":True}
    f=build_frame("diagnose reporting",u,memory,{},None)
    assert f.case["symptoms"]==["stops reporting"] and f.case["affected_scope"]=="multiple devices"
