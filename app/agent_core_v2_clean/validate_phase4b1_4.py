import json
from copy import deepcopy
from pathlib import Path
from .agent import _is_structurally_social
from .models import TurnUnderstanding
from .unified_evidence_authority import apply_unified_evidence_verdict
from .documented_answer import evidence_pack


def _u(**overrides):
    base=dict(user_act="new_request",intent="conceptual",topic_relation="new_topic",domain_relevance="in_scope",current_goal="",goal_complete=True,goal_updates={},case_updates=[],needs_clarification=False,clarification_target=None,should_retrieve=False,confidence=.9,reasoning_summary="",degraded=False,canonical_subject=None,subject_origin="none",reference_relation="none",requested_workflow="none")
    base.update(overrides);return TurnUnderstanding(**base)


def run(session_path):
    data=json.loads(Path(session_path).read_text(encoding="utf-8"))
    first=data["turns"][0];last=data["turns"][-1]
    raw=json.loads(first["provider_trace"]["understanding"]["text"])
    raw["goal_updates"]={k:v for k,v in (raw.get("goal_updates") or {}).items() if k=="operation"}
    social,_=_is_structurally_social(_u(**{k:v for k,v in raw.items() if k in _u().__dict__}))
    retrieval=deepcopy(last["retrieval"])
    retrieval["diagnostic_evidence"]=deepcopy(last["retrieval"]["diagnostic_evidence"])
    fixed=apply_unified_evidence_verdict(retrieval,last["input"],last["understanding"])
    pack=evidence_pack(fixed,last["input"],last["understanding"])
    packed=" ".join(x.get("text","") for x in pack).casefold()
    selected=" ".join(x.get("text","") for x in fixed["evidence_verdict"]["selected_evidence"]).casefold()
    checks={
      "observed_greeting_drift_recovered":social,
      "greeting_retrieval_not_required_by_raw_contract":raw.get("should_retrieve") is False,
      "current_tls_chunk_selected":"5222" in selected and "tls" in selected,
      "current_tls_chunk_reaches_answer_pack":"5222" in packed and "tls" in packed,
      "primary_document_identity_preserved":len(fixed["evidence_verdict"]["document_ids"])==1,
      "followup_grounding_accepted":fixed["evidence_verdict"]["accepted"] is True,
    }
    failed=[k for k,v in checks.items() if not v]
    return {"phase":"4B.1.4","passed":len(checks)-len(failed),"failed":len(failed),"checks":checks}

if __name__=="__main__":
    import sys
    result=run(sys.argv[1]);print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(1 if result["failed"] else 0)
