from __future__ import annotations
from typing import Any, Callable
from .evidence_budget import select_evidence
from .evidence_recovery import classify_generation_failure, build_evidence_backed_recovery

def compose_resiliently(*, intent: str, evidence: dict[str,Any], compose: Callable[[dict[str,Any]],dict[str,Any]]) -> tuple[dict[str,Any],dict[str,Any]]:
 selection=select_evidence(evidence,intent)
 try:
  answer=compose({**evidence,"selected_for_answer":selection["selected"],"citable":selection["selected"]})
  answer=answer if isinstance(answer,dict) else {"mode":"natural_conversation","text":str(answer)}
  reason=classify_generation_failure(finish_reason=answer.get("finish_reason"),answer_text=answer.get("text"))
  if reason:return build_evidence_backed_recovery(selection,failure_reason=reason),selection
  return answer,selection
 except Exception as exc:
  reason=classify_generation_failure(error=exc) or "unknown_generation_failure"
  return build_evidence_backed_recovery(selection,failure_reason=reason),selection
