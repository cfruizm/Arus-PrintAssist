"""Single integration surface used by interpreter, evidence pipeline and response composer."""
from .intent_reconciler import reconcile
from .coverage_controller import assess_coverage, same_document_query
from .answer_policy import HYBRID_ANSWER_INSTRUCTIONS, answer_mode, knowledge_flags, sanitize_visible_answer

def reconcile_interpretation(interpreter,message,state,raw):
    fixed,trace=reconcile(interpreter.gateway,message,state,raw)
    interpreter.last_trace["intent_reconciliation"]=trace
    return fixed

def enrich_answer_payload(payload,coverage):
    out=dict(payload);out["coverage"]=coverage;out["instructions"]=list(out.get("instructions") or [])+HYBRID_ANSWER_INSTRUCTIONS;return out
