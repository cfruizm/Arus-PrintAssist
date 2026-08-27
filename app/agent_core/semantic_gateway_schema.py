from __future__ import annotations
SEMANTIC_DECISION_SCHEMA={
 "type":"object","additionalProperties":False,
 "properties":{
  "route":{"type":"string","enum":["social","capabilities","support_intake","case_update","clarification","technical_query","technical_follow_up","explicit_source","escalation","out_of_scope"]},
  "intent":{"type":"string","enum":["social","conceptual","procedural","troubleshooting","requirements","warranty","architecture","escalation","unknown"]},
  "confidence":{"type":"number","minimum":0,"maximum":1},
  "next_action":{"type":"string","enum":["respond_deterministically","update_case","ask_clarification","retrieve","escalate","legacy_fallback"]},
  "requires_retrieval":{"type":"boolean"},"requires_clarification":{"type":"boolean"},"requires_escalation":{"type":"boolean"},"topic_shift":{"type":"boolean"},
  "case_updates":{"type":"array","maxItems":6,"items":{"type":"object","additionalProperties":False,"properties":{"type":{"type":"string","enum":["product","process","symptom","attempted_action","attempt_result","affected_scope","error_message","evidence","technical_context","resolution_status"]},"value":{"type":"string","maxLength":500},"confidence":{"type":"number","minimum":0,"maximum":1}},"required":["type","value","confidence"]}},
  "missing_information":{"type":"array","maxItems":5,"items":{"type":"string","maxLength":200}},
  "clarification_question":{"type":["string","null"],"maxLength":500},
  "retrieval_request":{"anyOf":[{"type":"null"},{"type":"object","additionalProperties":False,"properties":{"intent":{"type":"string"},"products":{"type":"array","items":{"type":"string"}},"processes":{"type":"array","items":{"type":"string"}},"problem_statement":{"type":["string","null"]},"question":{"type":["string","null"]},"exclude_actions":{"type":"array","items":{"type":"string"}}},"required":["intent","products","processes","problem_statement","question","exclude_actions"]}]},
  "reasoning_summary":{"type":"string","maxLength":160}
 },
 "required":["route","intent","confidence","next_action","requires_retrieval","requires_clarification","requires_escalation","topic_shift","case_updates","missing_information","clarification_question","retrieval_request","reasoning_summary"]
}
