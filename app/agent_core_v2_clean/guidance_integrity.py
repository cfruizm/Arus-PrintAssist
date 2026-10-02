from __future__ import annotations
from copy import deepcopy

RISK_POLICY_VERSION = "guidance_integrity_v2_semantic"


def _text(value):
    return " ".join(str(value or "").split()).strip()


def _attempts(retrieval):
    rows=[]
    context=(retrieval or {}).get("_case_context") or {}
    for item in context.get("attempts") or []:
        action=_text((item or {}).get("action"))
        if not action:continue
        rows.append({
            "action":action,
            "result":_text((item or {}).get("result")) or None,
            "outcome":_text((item or {}).get("outcome")) or "unknown",
            "authority":"user_confirmed_case_memory",
        })
    return rows[-8:]


def _guidance(retrieval):
    previous=(retrieval or {}).get("_answer_context") or {}
    rows=[]
    for item in previous.get("delivered_guidance") or []:
        action=_text((item or {}).get("action"))
        if action:
            rows.append({
                "action":action,
                "status":_text((item or {}).get("status")) or "delivered",
                "authority":"assistant_recommendation_only",
                "semantic_signature":list((item or {}).get("semantic_signature") or []),
                "excerpt":_text((item or {}).get("excerpt")) or None,
            })
    return rows[-8:]


def build_guidance_integrity_contract(retrieval):
    confirmed=_attempts(retrieval)
    delivered=_guidance(retrieval)
    return {
        "schema_version":1,
        "policy_version":RISK_POLICY_VERSION,
        "user_confirmed_attempts":deepcopy(confirmed),
        "assistant_delivered_guidance":deepcopy(delivered),
        "response_policy":{
            "exclude_previous_guidance":bool(delivered),
            "semantic_equivalence_required":True,
            "repeat_full_instructions":False,
            "when_no_new_actions":"State briefly that the authorized material contains no additional steps; do not restate completed guidance.",
        },
        "authority_rules":[
            "Only user_confirmed_attempts may be described as performed, completed, checked or verified by the user.",
            "assistant_delivered_guidance means recommendation shown previously, not action performed.",
            "Never infer execution from prior recommendation, citation, document presence or conversational continuity.",
            "Treat paraphrases with the same action, object and intended result as already delivered guidance.",
            "When only remaining steps are requested, exclude semantically equivalent prior guidance and answer briefly if none remain.",
            "If execution is not confirmed, use prospective language and preserve that check as pending.",
        ],
        "disruptive_guidance_policy":{
            "semantic_criteria":[
                "possible loss of configuration, data or recoverability",
                "possible interruption of a service or broad user impact",
                "security, authentication, authorization or access-control change",
                "difficult rollback, irreversible state change or dependency on a maintenance window",
            ],
            "required_elements":[
                "present only after lower-impact checks unless documentation requires another order",
                "state the condition under which the action becomes appropriate",
                "state the likely impact and scope",
                "state backup, rollback or recoverability prerequisites when applicable",
                "state authorization or maintenance-window prerequisites when applicable",
                "offer escalation when prerequisites or safe execution cannot be confirmed",
            ],
            "never_present_as":"routine first-line action without safeguards",
        },
    }


def integrity_diagnostic(contract):
    return {
        "policy_version":contract.get("policy_version"),
        "confirmed_attempt_count":len(contract.get("user_confirmed_attempts") or []),
        "delivered_guidance_count":len(contract.get("assistant_delivered_guidance") or []),
        "confirmed_and_delivered_separated":True,
        "disruptive_guidance_guard_enabled":True,
    }
