from __future__ import annotations

CONVERSATION_ACTS = [
    "social_message",
    "request_capabilities",
    "request_support",
    "provide_case_detail",
    "report_failed_attempt",
    "report_failed_attempt_and_request_next_step",
    "request_next_step",
    "ask_technical_question",
    "provide_explicit_source",
    "request_escalation",
    "ambiguous_reference",
    "change_topic",
    "out_of_scope"
]

SEMANTIC_DECISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "conversation_act": {"type": "string", "enum": CONVERSATION_ACTS},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "state_updates": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string", "enum": [
                        "product", "process", "symptom", "attempted_action",
                        "attempt_result", "affected_scope", "error_message",
                        "evidence", "technical_context", "resolution_status"
                    ]},
                    "value": {"type": "string", "maxLength": 400},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["type", "value", "confidence"]
            }
        },
        "response_mode": {"type": "string", "enum": [
            "deterministic", "clarification", "retrieve", "escalate", "legacy_fallback"
        ]},
        "retrieval_request": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "products": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
                        "processes": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
                        "problem_statement": {"type": ["string", "null"], "maxLength": 500},
                        "question": {"type": ["string", "null"], "maxLength": 500},
                        "exclude_actions": {"type": "array", "maxItems": 5, "items": {"type": "string"}}
                    },
                    "required": ["products", "processes", "problem_statement", "question", "exclude_actions"]
                }
            ]
        },
        "clarification_question": {"type": ["string", "null"], "maxLength": 300},
        "topic_shift": {"type": "boolean"},
        "reasoning_summary": {"type": "string", "maxLength": 80}
    },
    "required": [
        "conversation_act", "confidence", "state_updates", "response_mode",
        "retrieval_request", "clarification_question", "topic_shift",
        "reasoning_summary"
    ]
}
