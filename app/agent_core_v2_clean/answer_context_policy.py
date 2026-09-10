from __future__ import annotations

FOLLOW_UP_ACTS={"follow_up","answer_to_question","attempt_result","reported_failure"}
PREVIOUS_ANSWER_EXCERPT_CHARS=420
MAX_SOURCE_TITLES=3

def _confirmed_facts(understanding):
    updates=dict((understanding or {}).get("goal_updates") or {})
    structural={"intent","status","summary","known_details","missing_detail","goal_complete","current_goal","topic"}
    return [{"key":str(k),"value":str(v),"origin":"user","status":"confirmed"} for k,v in updates.items() if str(k) not in structural and str(v).strip()]

def enrich_internal_payload(payload,answer_context,understanding):
    out=dict(payload or {});u=understanding or {};follow=u.get("user_act") in FOLLOW_UP_ACTS
    confirmed=_confirmed_facts(u)
    out["scope_contract"]={
        "confirmed_facts":confirmed,
        "evidence_is_not_user_confirmation":True,
        "conditional_guidance_required_for_unconfirmed_scenarios":True,
        "max_indispensable_questions":1,
    }
    if follow and answer_context:
        closing=str(answer_context.get("closing_question") or "").strip() or None
        out["previous_answer_context"]={
            "goal":answer_context.get("goal"),
            "answer_mode":answer_context.get("answer_mode"),
            "main_text_excerpt":" ".join(str(answer_context.get("main_text_excerpt") or "").split())[:PREVIOUS_ANSWER_EXCERPT_CHARS],
            "closing_question":closing,
            "source_titles":list(answer_context.get("source_titles") or [])[:MAX_SOURCE_TITLES],
            "partial":bool(answer_context.get("partial")),
        }
        out["scope_contract"]["previous_choice_request_unanswered"]=bool(closing and u.get("user_act")=="follow_up")
        out["scope_contract"]["previous_choice_request"]=closing
        out["continuity_instruction"]=(
            "Answer only the current follow-up. Evidence describes possibilities, not user-confirmed choices. "
            "If the previous answer asked the user to choose a scenario and the current message did not answer it, "
            "give common checks first, label scenario-specific checks conditionally, and ask only the unresolved "
            "choice that materially changes the procedure. Respect confirmed facts."
        )
    return out
