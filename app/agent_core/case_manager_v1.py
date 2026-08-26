from __future__ import annotations
import re
from app.agent_core.router_models import ContextFact, RouterShadowState
from app.agent_core.router_normalizer import normalize_conversation_text

FAILED_PATTERNS=(r"\bno funcion",r"\bsigue igual\b",r"\bcontinua igual\b",r"\bpersiste\b",r"\bno resolv",r"\bno sirvio\b")
SUCCESS_PATTERNS=(r"\bya funciono\b",r"\bquedo resuelto\b",r"\bse soluciono\b",r"\bproblema resuelto\b")
ACTION_PATTERNS=(r"\bya (?:lo|eso) (?:hice|realice|probe|valide|intente)\b",r"\bya (?:hice|realice|probe|valide|reinicie|reinstale|actualice)\b",r"\brealice el proceso\b")
DETAIL_PATTERNS=(r"\bsolo\b",r"\bsolamente\b",r"\bespecificamente\b",r"\bpero\b",r"\bdespues de\b",r"\bantes de\b")
IMPACT_PATTERNS=((r"\bvarios usuarios\b|\btodos los usuarios\b","multiple_users"),(r"\bun usuario\b|\bsolo un usuario\b","single_user"))
NEGATIVE_EVIDENCE=(r"\bno aparece (?:ningun|un) (?:mensaje|codigo) de error\b",r"\bsin (?:mensaje|codigo) de error\b")


def is_case_update_candidate(message: str, state: RouterShadowState) -> bool:
    if not state.technical_case.is_active: return False
    text=normalize_conversation_text(message)
    patterns=FAILED_PATTERNS+SUCCESS_PATTERNS+ACTION_PATTERNS+DETAIL_PATTERNS+NEGATIVE_EVIDENCE
    if any(re.search(pattern,text) for pattern in patterns): return True
    if any(re.search(pattern,text) for pattern,_ in IMPACT_PATTERNS): return True
    return len(text.split()) <= 14 and not any(word in text.split()[:2] for word in ("que","como","cual","cuando","donde"))


def infer_updates(message: str) -> tuple[list[ContextFact],dict]:
    text=normalize_conversation_text(message); updates=[]; derived={}
    failed=any(re.search(p,text) for p in FAILED_PATTERNS); succeeded=any(re.search(p,text) for p in SUCCESS_PATTERNS) and not failed
    attempted=any(re.search(p,text) for p in ACTION_PATTERNS)
    if attempted: updates.append(ContextFact("attempted_action",message.strip(),0.9))
    if failed: updates.append(ContextFact("attempt_result","failed",0.98)); derived.update(resolution_status="unresolved",case_status="unresolved")
    elif succeeded: updates.append(ContextFact("attempt_result","successful",0.98)); derived.update(resolution_status="resolved",case_status="resolved")
    for pattern,value in IMPACT_PATTERNS:
        if re.search(pattern,text): updates.append(ContextFact("affected_scope",value,0.95)); derived["affected_users"]=value; break
    if any(re.search(p,text) for p in NEGATIVE_EVIDENCE): updates.append(ContextFact("negative_evidence","no_error_message",0.95))
    if any(re.search(p,text) for p in DETAIL_PATTERNS): updates.append(ContextFact("technical_context",message.strip(),0.8))
    if not updates: updates.append(ContextFact("technical_context",message.strip(),0.65))
    return updates,derived


def apply_updates(state: RouterShadowState, updates: list[ContextFact], derived: dict) -> None:
    case=state.technical_case
    for fact in updates:
        if fact.fact_type=="attempted_action": case.attempted_actions.append(fact.value)
        elif fact.fact_type=="attempt_result" and fact.value=="failed" and case.attempted_actions: case.failed_actions.append(case.attempted_actions[-1])
        else: case.context_facts.append(fact)
    if derived.get("resolution_status"): case.resolution_status=derived["resolution_status"]
    if derived.get("case_status"): case.status=derived["case_status"]
    if derived.get("affected_users"): case.affected_users=derived["affected_users"]
