from copy import deepcopy
import secrets
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway, reset_gateway_session
from .models import ConversationMemory
from .understanding import ConversationUnderstanding
from .policy import ConversationPolicy
from .response import NaturalResponseComposer
from .agent import CleanConversationalAgent
from .telemetry import empty, normalize, add_result, snapshot
from .budget import BudgetPolicy
from .retrieval import RetrievalQueryBuilder, ReadOnlyRetrieval, retrieval_summary
from .documented_answer import DocumentedAnswerComposer, answer_fingerprint, PROMPT_VERSION
from .documented_router import maybe_generate_procedural
from .semantic_fit import apply_semantic_fit, capture_answer_context

KEY = "agent_core_v2_clean_store"

def _context_key(message, memory):
    return "|".join((" ".join(str(message).split()).casefold(), str(memory.active_topic or "").strip().casefold(), str(memory.pending_goal.summary or "").strip().casefold()))

def _artifact(result):
    return {k: deepcopy(result.get(k)) for k in ("understanding", "understanding_contract", "goal_update_normalization", "decision", "answer", "retrieval", "documented_answer", "procedural_answer", "internal_knowledge", "procedural_recovery", "answer_context")}

def _zero():
    return {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "provider_failed_calls": 0, "contract_failed_calls": 0, "functional_failed_calls": 0}

def get_store(s):
    if KEY not in s:
        s[KEY] = {"session_id": secrets.token_hex(12), "memory": ConversationMemory(), "messages": [], "turns": [], "errors": [], "telemetry": empty(), "budget": BudgetPolicy.for_mode("normal").to_dict(), "deterministic_results": [], "exact_turn_cache": {}, "retrieval_cache": {}, "documented_answer_cache": {}, "procedural_answer_cache": {}, "cache_metrics": {}, "answer_context": {}}
    x = s[KEY]
    x["telemetry"] = normalize(x.get("telemetry"))
    for k in ("exact_turn_cache", "retrieval_cache", "documented_answer_cache", "procedural_answer_cache"):
        x.setdefault(k, {})
    x.setdefault("answer_context", {})
    x.setdefault("cache_metrics", {})
    for k in ("hits", "calls_avoided", "tokens_avoided_estimate", "retrieval_hits", "documented_answer_hits", "procedural_answer_hits", "internal_knowledge_hits"):
        x["cache_metrics"].setdefault(k, 0)
    for k, d in (("deterministic_results", []), ("errors", []), ("turns", []), ("messages", [])):
        x.setdefault(k, d)
    return x

def reset_store(s):
    reset_gateway_session(s)
    s.pop(KEY, None)
    return get_store(s)

def _gateway(secrets_obj, s):
    return LLMGateway(load_gateway_config(secrets_obj), s)

def build_agent(secrets_obj, s, budget):
    g = _gateway(secrets_obj, s)
    return CleanConversationalAgent(ConversationUnderstanding(g, budget.understanding_max_tokens), ConversationPolicy(), NaturalResponseComposer(g, budget.response_max_tokens))

def _attach_retrieval(result, message, store):
    if (result.get("decision") or {}).get("action") != "defer_to_retrieval":
        return result
    try:
        u = type("U", (), result.get("understanding") or {})()
        builder = RetrievalQueryBuilder()
        query = builder.build(message, store["memory"], u)
        current = builder.current_only(message, u)
        cached = store["retrieval_cache"].get(query.fingerprint)
        if cached:
            raw = deepcopy(cached)
            raw["cache_hit"] = True
            store["cache_metrics"]["retrieval_hits"] += 1
        else:
            raw = ReadOnlyRetrieval(k=6).search(query, current)
            raw["cache_hit"] = False
            store["retrieval_cache"][query.fingerprint] = deepcopy(raw)
        retrieval = apply_semantic_fit(raw, store.get("answer_context"))
        retrieval["_answer_context"] = deepcopy(store.get("answer_context") or {})
    except Exception as exc:
        retrieval = {"enabled": True, "ok": False, "llm_called": False, "production_changed": False, "count": 0, "evidence": [], "errors": [{"type": type(exc).__name__, "message": str(exc)}]}
    result["retrieval"] = retrieval
    result["answer"]["text"] = retrieval_summary(retrieval)
    result["answer"]["mode"] = "retrieval_diagnostic" if retrieval.get("ok") else "retrieval_error"
    return result

def _conceptual(result, message, secrets_obj, s, budget, store):
    if (result.get("decision") or {}).get("action") != "defer_to_retrieval":
        return result, {"skipped": True, "reason": "decision_does_not_authorize_retrieval"}
    retrieval = result.get("retrieval") or {}
    understanding = result.get("understanding") or {}
    if understanding.get("intent") != "conceptual" or not retrieval.get("ok") or not retrieval.get("evidence"):
        return result, None
    model = str(getattr(load_gateway_config(secrets_obj), "model", "") or "")
    key = answer_fingerprint(message, understanding, retrieval, model)
    cached = store["documented_answer_cache"].get(key)
    if cached:
        result["answer"] = deepcopy(cached["answer"])
        result["documented_answer"] = {**deepcopy(cached["diagnostic"]), "cache_hit": True}
        store["cache_metrics"]["documented_answer_hits"] += 1
        return result, {"skipped": True, "reason": "documented_answer_cache"}
    allowed, _ = budget.can_call(store["telemetry"], estimated_tokens=1100)
    if not allowed:
        return result, None
    composer = DocumentedAnswerComposer(_gateway(secrets_obj, s), 260)
    answer = composer.compose(message, understanding, retrieval)
    payload = answer.to_dict()
    payload.update({"documented_evidence_used": answer.mode in {"documented_answer", "documented_answer_partial"}, "internal_knowledge_used": False, "knowledge_mode": "documented_only" if answer.mode in {"documented_answer", "documented_answer_partial"} else "none"})
    result["answer"] = payload
    diagnostic = {"enabled": True, "cache_hit": False, "prompt_version": PROMPT_VERSION, "quality_budget_preserved": True, "semantic_fit": retrieval.get("semantic_fit")}
    result["documented_answer"] = diagnostic
    if answer.mode in {"documented_answer", "documented_answer_partial"}:
        store["memory"].pending_goal.status = "complete" if answer.mode == "documented_answer" else "partially_answered"
        result["state_after"] = deepcopy(store["memory"].to_dict())
        if answer.mode == "documented_answer":
            store["documented_answer_cache"][key] = {"answer": deepcopy(payload), "diagnostic": deepcopy(diagnostic)}
    return result, composer.last_provider_result

def _answers(result, message, secrets_obj, s, budget, store):
    if (result.get("decision") or {}).get("action") != "defer_to_retrieval":
        skipped = {"skipped": True, "reason": "decision_does_not_authorize_retrieval"}
        return result, skipped, skipped
    result, conceptual_trace = _conceptual(result, message, secrets_obj, s, budget, store)
    result, procedural_trace = maybe_generate_procedural(result, message, _gateway(secrets_obj, s), budget, store, str(getattr(load_gateway_config(secrets_obj), "model", "") or ""))
    return result, conceptual_trace, procedural_trace

def _trace_list(value):
    if not value:
        return []
    return [x for x in (value if isinstance(value, list) else [value]) if x]

def _apply_answer_traces(result, conceptual, procedural, store):
    traces = _trace_list(conceptual) + _trace_list(procedural)
    result.setdefault("provider_trace", {}).update({"documented_answer": conceptual or {"skipped": True, "reason": "documented_answer_not_called"}, "procedural_answer": procedural or {"skipped": True, "reason": "procedural_answer_not_called"}})
    recorded = []
    for trace in traces:
        if trace.get("skipped"):
            continue
        attempts = trace.get("attempts") or []
        if attempts:
            for attempt in attempts:
                add_result(store["telemetry"], attempt)
                recorded.append(attempt)
        else:
            add_result(store["telemetry"], trace)
            recorded.append(trace)
    return recorded

def _combined_turn_metrics(base_traces, generated_traces):
    items = [x for x in (base_traces or []) if x and not x.get("skipped")] + [x for x in generated_traces if x and not x.get("skipped")]
    out = _zero()
    out["calls"] = len(items)
    for item in items:
        usage = item.get("usage") or {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            out[key] += int(usage.get(key, 0) or 0)
        if item.get("ok") is False:
            out["provider_failed_calls"] += 1
    return out

def _cacheable_final(result):
    answer = result.get("answer") or {}
    return answer.get("mode") in {"documented_answer", "procedural_documented_answer", "controlled_internal_knowledge"} and str(answer.get("finish_reason") or "").casefold() not in {"length", "max_tokens"}

def _finalize_answer_context(result, store):
    context = capture_answer_context(result)
    if context:
        store["answer_context"] = context
        result["answer_context"] = deepcopy(context)

def process_message(message, secrets_obj, s):
    store = get_store(s)
    budget = BudgetPolicy(**store["budget"])
    memory_before = deepcopy(store["memory"])
    before = deepcopy(store["memory"].to_dict())
    key = _context_key(message, store["memory"])
    cached = store["exact_turn_cache"].get(key)
    execution = {"mode": budget.mode, "understanding_budget": budget.understanding_max_tokens, "response_budget": budget.response_max_tokens}
    if cached:
        store["memory"].turn_number += 1
        result = {"input": message, "state_before": before, **deepcopy(cached["artifact"]), "state_after": deepcopy(store["memory"].to_dict()), "provider_trace": {"understanding": {"skipped": True, "reason": "exact_turn_cache"}, "response": {"skipped": True, "reason": "exact_turn_cache"}}, "execution": {**execution, "cache_hit": True}, "cache": {"hit": True, "type": "exact_turn"}, "production_changed": False}
        result, conceptual, procedural = _answers(result, message, secrets_obj, s, budget, store)
        traces = _apply_answer_traces(result, conceptual, procedural, store)
        result["turn_metrics"] = _combined_turn_metrics([], traces)
        _finalize_answer_context(result, store)
        result["session_metrics_after_turn"] = snapshot(store["telemetry"])
        text = result["answer"]["text"]
        store["cache_metrics"]["hits"] += 1
        store["cache_metrics"]["calls_avoided"] += 1
        store["messages"] += [{"role": "user", "content": message}, {"role": "assistant", "content": text}]
        store["turns"].append(result)
        return result
    allowed, _ = budget.can_call(store["telemetry"])
    if not allowed:
        return {"input": message, "blocked": True, "answer": {"text": "La prueba no se ejecutó porque alcanzaría el presupuesto configurado.", "mode": "budget_block", "knowledge_used": False}, "turn_metrics": _zero(), "execution": execution, "production_changed": False}
    store["messages"].append({"role": "user", "content": message})
    try:
        result = build_agent(secrets_obj, s, budget).process(message, store["memory"])
        result = _attach_retrieval(result, message, store)
        base = result.get("provider_trace") or {}
        contract = (result.get("understanding_contract") or {}).get("valid")
        add_result(store["telemetry"], base.get("understanding"), contract)
        add_result(store["telemetry"], base.get("response"))
        result, conceptual, procedural = _answers(result, message, secrets_obj, s, budget, store)
        traces = _apply_answer_traces(result, conceptual, procedural, store)
        base_traces = [x for x in (base.get("understanding"), base.get("response")) if x and not x.get("skipped")]
        result["turn_metrics"] = _combined_turn_metrics(base_traces, traces)
        _finalize_answer_context(result, store)
        result["session_metrics_after_turn"] = snapshot(store["telemetry"])
        result["execution"] = {**execution, "cache_hit": False}
        result["cache"] = {"hit": False}
        text = result["answer"]["text"]
        if contract and _cacheable_final(result):
            entry = {"artifact": _artifact(result), "tokens_estimate": result["turn_metrics"].get("total_tokens", 0)}
            store["exact_turn_cache"][key] = entry
            store["exact_turn_cache"][_context_key(message, store["memory"])] = entry
    except Exception as exc:
        store["memory"] = memory_before
        store["errors"].append({"turn": store["memory"].turn_number + 1, "message": message, "error_type": type(exc).__name__, "error": str(exc)})
        text = "No pude procesar este turno. El error quedó registrado."
        result = {"input": message, "error": {"type": type(exc).__name__, "message": str(exc)}, "execution": execution, "production_changed": False}
    store["messages"].append({"role": "assistant", "content": text})
    store["turns"].append(result)
    return result

def export_session(s):
    x = get_store(s)
    return {"format": "agent_core_v2_clean_phase3a4", "session_id": x.get("session_id"), "gateway_budget": {"calls": int(s.get("llm_gateway_calls", 0)), "tokens": int(s.get("llm_gateway_tokens", 0))}, "messages": deepcopy(x["messages"]), "turns": deepcopy(x["turns"]), "state": x["memory"].to_dict(), "answer_context": deepcopy(x.get("answer_context") or {}), "budget": deepcopy(x["budget"]), "telemetry": snapshot(x["telemetry"]), "cache_metrics": deepcopy(x["cache_metrics"]), "errors": deepcopy(x["errors"]), "retrieval_enabled": True, "documented_answer_enabled": True, "procedural_answer_enabled": True, "production_changed": False}
