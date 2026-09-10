from __future__ import annotations

def enrich_internal_payload(payload,answer_context,understanding):
 out=dict(payload or {});u=understanding or {};follow=u.get("user_act") in {"follow_up","answer_to_question","attempt_result","reported_failure"}
 if follow and answer_context:
  out["previous_answer_context"]={"goal":answer_context.get("goal"),"answer_mode":answer_context.get("answer_mode"),"main_text_excerpt":answer_context.get("main_text_excerpt"),"source_titles":answer_context.get("source_titles"),"cited_ids":answer_context.get("cited_ids"),"cited_evidence":answer_context.get("cited_evidence"),"partial":answer_context.get("partial")}
  out["continuity_instruction"]="Answer the current follow-up about the previous answer. Validate or qualify prior guidance instead of restarting with a generic checklist. Treat facts already confirmed in conversation as confirmed. Do not ask for them again or replace a confirmed product/platform with operating-system assumptions. Preserve the exact scope of prior guidance. If a scenario remains unconfirmed, ask only for that missing scenario."
 return out
