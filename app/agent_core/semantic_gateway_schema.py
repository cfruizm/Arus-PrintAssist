from __future__ import annotations

SEMANTIC_DECISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "route": {"type": "string", "enum": [
            "social", "capabilities", "support_intake", "case_update",
            "clarification", "technical_query", "technical_follow_up",
            "explicit_source", "escalation", "out_of_scope"
        ]},
        "intent": {"type": "string", "enum": [
            "social", "conceptual", "procedural", "troubleshooting",
            "requirements", "warranty", "architecture", "escalation", "unknown"
        ]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "state_updates": {
            "type": "array", "maxItems": 5,
            "items": {
                "type": "object", "additionalProperties": False,
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
        "requires_retrieval": {"type": "boolean"},
        "requires_clarification": {"type": "boolean"},
        "requires_escalation": {"type": "boolean"},
        "topic_shift": {"type": "boolean"},
        "missing_information": {
            "type": "array", "maxItems": 3,
            "items": {"type": "string", "maxLength": 120}
        },
        "clarification_question": {"type": ["string", "null"], "maxLength": 300},
        "retrieval_request": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "intent": {"type": "string"},
                        "products": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
                        "processes": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
                        "problem_statement": {"type": ["string", "null"], "maxLength": 500},
                        "question": {"type": ["string", "null"], "maxLength": 500},
                        "exclude_actions": {"type": "array", "maxItems": 5, "items": {"type": "string"}}
                    },
                    "required": ["intent", "products", "processes", "problem_statement", "question", "exclude_actions"]
                }
            ]
        },
        "reasoning_summary": {"type": "string", "maxLength": 80}
    },
    "required": [
        "route", "intent", "confidence", "state_updates", "response_mode",
        "requires_retrieval", "requires_clarification", "requires_escalation",
        "topic_shift", "missing_information", "clarification_question",
        "retrieval_request", "reasoning_summary"
    ]
}
