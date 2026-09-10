from __future__ import annotations

FOLLOW_UP_ACTS = {"follow_up", "answer_to_question", "attempt_result", "reported_failure"}
PREVIOUS_ANSWER_EXCERPT_CHARS = 420
MAX_SOURCE_TITLES = 3


def enrich_internal_payload(payload, answer_context, understanding):
    out = dict(payload or {})
    u = understanding or {}
    follow = u.get("user_act") in FOLLOW_UP_ACTS

    if follow and answer_context:
        out["previous_answer_context"] = {
            "goal": answer_context.get("goal"),
            "answer_mode": answer_context.get("answer_mode"),
            "main_text_excerpt": " ".join(
                str(answer_context.get("main_text_excerpt") or "").split()
            )[:PREVIOUS_ANSWER_EXCERPT_CHARS],
            "source_titles": list(answer_context.get("source_titles") or [])[:MAX_SOURCE_TITLES],
            "partial": bool(answer_context.get("partial")),
        }
        out["continuity_instruction"] = (
            "Answer only the current follow-up. Use the authorized evidence supplied "
            "in the main payload. Respect confirmed facts. Do not promote an "
            "unconfirmed scenario to fact. Ask at most one indispensable missing fact."
        )

    return out
