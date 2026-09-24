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
from .conceptual_route import must_preempt_documented_answer
from .semantic_fit import apply_semantic_fit, capture_answer_context
from .unified_evidence_authority import apply_unified_evidence_verdict
from .response_reconciler import reconcile
from .topic_boundary import infer_topic_boundary
from .operational_coherence import normalize_generation_flags
from .canonical_frame_shadow import build_shadow_frame, enrich_shadow_frame, refresh_shadow_diagnostics, STORE_KEY as CANONICAL_FRAME_KEY, REGISTRY_KEY as CANONICAL_REGISTRY_KEY
from .canonical_query import apply_canonical_query

KEY = "agent_core_v2_clean_store"

def _safe_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_safe_text(x) for x in value if _safe_text(x))
    if isinstance(value, dict):
        for key in ("summary", "subject", "operation", "product", "value", "text"):
            if key in value and value.get(key) is not None:
                return _safe_text(value.get(key))
        return ""
    return str(value)

def _stabilize_memory_text(memory):
    memory.active_topic = _safe_text(getattr(memory, "active_topic", None)) or None
    goal = getattr(memory, "pending_goal", None)
    if goal is not None:
        goal.summary = _safe_text(getattr(goal, "summary", ""))
        if hasattr(goal, "missing_detail"):
            goal.missing_detail = _safe_text(getattr(goal, "missing_detail", "")) or None
    memory.last_assistant_question = _safe_text(getattr(memory, "last_assistant_question", None)) or None
    return memory

def _context_key(message, memory):
    return "|".join((" ".join(_safe_text(message).split()).casefold(), _safe_text(memory.active_topic).strip().casefold(), _safe_text(memory.pending_goal.summary).strip().casefold()))

def _artifact(result):
    return {k: deepcopy(result.get(k)) for k in ("understanding", "understanding_contract", "goal_update_normalization", "decision", "answer", "retrieval", "documented_answer", "procedural_answer", "internal_knowledge", "procedural_recovery", "answer_context", "canonical_conversation_frame", "canonical_divergences", "canonical_query_authority")}

def _zero():
    return {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "provider_failed_calls": 0, "contract_failed_calls": 0, "functional_failed_calls": 0}

def get_store(s):
    if KEY not in s:
        s[KEY] = {"session_id": secrets.token_hex(12), "memory": ConversationMemory(), "messages": [], "turns": [], "errors": [], "telemetry": empty(), "budget": BudgetPolicy.for_mode("normal").to_dict(), "deterministic_results": [], "exact_turn_cache": {}, "retrieval_cache": {}, "documented_answer_cache": {}, "procedural_answer_cache": {}, "cache_metrics": {}, "answer_context": {}}
    x = s[KEY]
    x["memory"] = _stabilize_memory_text(x.get("memory") or ConversationMemory())
    x["telemetry"] = normalize(x.get("telemetry"))
    for k in ("exact_turn_cache", "retrieval_cache", "documented_answer_cache", "procedural_answer_cache"):
        x.setdefault(k, {})
    x.setdefault("answer_context", {})
    x.setdefault(CANONICAL_FRAME_KEY, {})
    x.setdefault(CANONICAL_REGISTRY_KEY, {})
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

def _model_profile(secrets_obj):
    config = load_gateway_config(secrets_obj)
    provider = config.get("provider")
    provider_config = (config.get("providers") or {}).get(provider, {})
    orchestrator = str(provider_config.get("orchestrator_model") or "")
    answer = str(provider_config.get("answer_model") or "")
    return {
        "provider": provider,
        "orchestrator_model": orchestrator,
        "answer_model": answer,
        "understanding_format": "text",
        "understanding_model_role": "orchestrator",
    }

def build_agent(secrets_obj, s, budget):
    g = _gateway(secrets_obj, s)
    return CleanConversationalAgent(ConversationUnderstanding(g, budget.understanding_max_tokens), ConversationPolicy(), NaturalResponseComposer(g, budget.response_max_tokens))

def _authorize_canonical_retrieval(result):
    u=result.get("understanding") or {};d=result.get("decision") or {}
    if u.get("should_retrieve") and d.get("action")=="diagnose":
        d["action"]="diagnose_with_retrieval";d["reason"]="canonical_technical_retrieval_authorized";result.setdefault("functional_events",[]).append({"type":"canonical_retrieval_authorization","severity":"info","previous_action":"diagnose"})
    return result

def _canonical_answer_context(store,result):
    frame=result.get(CANONICAL_FRAME_KEY) or {};topic=frame.get("topic") or {};tid=str(topic.get("topic_id") or "");rel=str(topic.get("relation") or "")
    record=(store.get(CANONICAL_REGISTRY_KEY) or {}).get(tid) or {};ctx=record.get("documented_context") or {}
    return deepcopy(ctx) if tid and rel in {"same_topic","same_topic_refinement","same_topic_candidate"} and ctx else deepcopy(store.get("answer_context") or {})
def _attach_retrieval(result, message, store):
    if (result.get("decision") or {}).get("action") not in {"defer_to_retrieval", "diagnose_with_retrieval"}:
        return result
    try:
        u = type("U", (), result.get("understanding") or {})()
        builder = RetrievalQueryBuilder()
        query = builder.build(message, store["memory"], u)
        current = builder.current_only(message, u)
        canonical_frame = result.get(CANONICAL_FRAME_KEY) or store.get(CANONICAL_FRAME_KEY) or {}
        query = apply_canonical_query(query, canonical_frame)
        current = apply_canonical_query(current, canonical_frame)
        answer_context = _canonical_answer_context(store, result)
        result["canonical_query_authority"] = {"enabled": True, "subject": (canonical_frame.get("subject") or {}).get("value"), "topic_id": (canonical_frame.get("topic") or {}).get("topic_id"), "documented_context_restored": bool(answer_context.get("cited_evidence"))}
        cached = store["retrieval_cache"].get(query.fingerprint)
        if cached:
            raw = deepcopy(cached)
            raw["cache_hit"] = True
            store["cache_metrics"]["retrieval_hits"] += 1
        else:
            raw = ReadOnlyRetrieval(k=6).search(query, current)
            raw["cache_hit"] = False
            store["retrieval_cache"][query.fingerprint] = deepcopy(raw)
        # Resolve the topic boundary before semantic fit. Understanding can label a
        # referential sub-question as new_topic even when it narrows the active goal.
        boundary = infer_topic_boundary(result.get("state_before") or {}, result.get("understanding") or {})
        canonical_topic = (canonical_frame.get("topic") or {})
        canonical_subject = (canonical_frame.get("subject") or {}).get("value")
        canonical_intent = (canonical_frame.get("operation") or {}).get("intent")
        if canonical_subject and canonical_topic.get("relation") in {"same_topic", "same_topic_refinement", "same_topic_candidate"}:
            boundary = type(boundary)("same_topic_refinement", "canonical_subject_continuity", boundary.shared_ratio, boundary.changed_dimensions, boundary.introduced_dimensions, "primary")
            result.setdefault("understanding", {})["topic_relation"] = "same_topic"
            if str(result["understanding"].get("intent") or "").casefold() in {"", "unknown"} and canonical_intent not in {None, "", "unknown"}:
                result["understanding"]["intent"] = canonical_intent
        result["topic_boundary"] = boundary.to_dict()
        raw.setdefault("query", {}).setdefault("fields", {})["topic_relation"] = boundary.relation
        raw["query"]["fields"]["previous_evidence_role"] = boundary.previous_evidence_role
        bridge_debug={"attempted":False}
        raw_quality=float(((raw.get("selection") or {}).get("quality") or 0.0))
        current_intent=str((result.get("understanding") or {}).get("intent") or "").casefold()
        prior_goal=str(answer_context.get("goal") or "").strip()
        prior_mode=str(answer_context.get("answer_mode") or "")
        if raw_quality < 0.35 and prior_goal and current_intent in {"conceptual","requirements"} and prior_mode in {"documented_answer","documented_answer_partial"}:
            bridge_query=builder.current_only((prior_goal+" "+message).strip(),u)
            bridge_query.fields["current_message"]=message;bridge_query.fields["context_mode"]="previous_answer_bridge";bridge_query.fields["user_act"]="follow_up";bridge_query.fields["topic_relation"]="same_topic_refinement";bridge_query.fields["previous_evidence_role"]="primary"
            bridge_raw=ReadOnlyRetrieval(k=6).search(bridge_query,bridge_query)
            bridge_quality=float(((bridge_raw.get("selection") or {}).get("quality") or 0.0))
            bridge_debug={"attempted":True,"prior_goal":prior_goal,"base_quality":raw_quality,"bridge_quality":bridge_quality,"selected":bridge_quality>raw_quality}
            if bridge_quality>raw_quality:
                raw=bridge_raw;boundary=type(boundary)("same_topic_refinement","low_quality_contextual_bridge",boundary.shared_ratio,boundary.changed_dimensions,boundary.introduced_dimensions,"primary")
                result["topic_boundary"]=boundary.to_dict();result["understanding"]["topic_relation"]="same_topic";result["understanding"]["user_act"]="follow_up"
        result.setdefault("generation_debug",{})["contextual_bridge"]=bridge_debug
        if boundary.relation in {"new_topic", "same_topic_changed_scope"} and not bool(result.get("canonical_query_authority",{}).get("documented_context_restored")):
            answer_context = {}
        retrieval = apply_semantic_fit(raw, answer_context)
        retrieval = apply_unified_evidence_verdict(retrieval, message, result.get("understanding") or {})
        retrieval["_answer_context"] = deepcopy(answer_context)
        retrieval["pre_retrieval_boundary"] = boundary.to_dict()
    except Exception as exc:
        retrieval = {"enabled": True, "ok": False, "llm_called": False, "production_changed": False, "count": 0, "evidence": [], "errors": [{"type": type(exc).__name__, "message": str(exc)}]}
    result["retrieval"] = retrieval
    result["answer"]["text"] = retrieval_summary(retrieval)
    result["answer"]["mode"] = "retrieval_diagnostic" if retrieval.get("ok") else "retrieval_error"
    return result

def _conceptual(result, message, secrets_obj, s, budget, store):
    if (result.get("decision") or {}).get("action") not in {"defer_to_retrieval", "diagnose_with_retrieval"}:
        return result, {"skipped": True, "reason": "decision_does_not_authorize_retrieval"}
    retrieval = result.get("retrieval") or {}
    understanding = result.get("understanding") or {}
    verdict = retrieval.get("evidence_verdict") or {}
    if not retrieval.get("ok") or not retrieval.get("evidence") or not verdict.get("accepted"):
        return result, None
    model = _model_profile(secrets_obj).get("answer_model", "")
    key = answer_fingerprint(message, understanding, retrieval, model)
    cached = store["documented_answer_cache"].get(key)
    if cached:
        result["answer"] = deepcopy(cached["answer"])
        result["documented_answer"] = {**deepcopy(cached["diagnostic"]), "cache_hit": True}
        store["cache_metrics"]["documented_answer_hits"] += 1
        return result, {"skipped": True, "reason": "documented_answer_cache"}
    allowed, block_reason = budget.can_call(store["telemetry"], estimated_tokens=1100)
    result.setdefault("generation_debug",{})["conceptual_call"]={"allowed":allowed,"block_reason":block_reason,"evidence_ids":verdict.get("evidence_ids") or []}
    if not allowed:return result,{"skipped":True,"reason":"conceptual_budget_block","block_reason":block_reason}
    intent = str(understanding.get("intent") or "").casefold()
    composer = DocumentedAnswerComposer(_gateway(secrets_obj, s), 680 if intent in {"procedural","requirements","troubleshooting"} else 420)
    answer = composer.compose(message, understanding, retrieval)
    payload = answer.to_dict()
    payload.update({"documented_evidence_used": answer.mode in {"documented_answer", "documented_answer_partial"}, "internal_knowledge_used": False, "knowledge_mode": "documented_only" if answer.mode in {"documented_answer", "documented_answer_partial"} else "none"})
    result["answer"] = payload
    diagnostic = {"enabled": True, "cache_hit": False, "prompt_version": PROMPT_VERSION, "quality_budget_preserved": True, "semantic_fit": retrieval.get("semantic_fit")}
    diagnostic["provider_debug"]={"ok":bool((composer.last_provider_result or {}).get("ok")),"finish_reason":(composer.last_provider_result or {}).get("finish_reason"),"usage":(composer.last_provider_result or {}).get("usage"),"token_budget_debug":((composer.last_provider_result or {}).get("metadata") or {}).get("token_budget_debug")}
    result["documented_answer"] = diagnostic
    if answer.mode in {"documented_answer", "documented_answer_partial"}:
        store["memory"].pending_goal.status = "complete" if answer.mode == "documented_answer" else "partially_answered"
        result["state_after"] = deepcopy(store["memory"].to_dict())
        if answer.mode == "documented_answer":
            store["documented_answer_cache"][key] = {"answer": deepcopy(payload), "diagnostic": deepcopy(diagnostic)}
    return result, composer.last_provider_result

def _answers(result, message, secrets_obj, s, budget, store):
    if (result.get("decision") or {}).get("action") not in {"defer_to_retrieval", "diagnose_with_retrieval"}:
        skipped={"skipped":True,"reason":"decision_does_not_authorize_retrieval"};return result,skipped,skipped
    retrieval=result.get("retrieval") or {};verdict=retrieval.get("evidence_verdict") or {}
    if verdict.get("accepted") and retrieval.get("generation_evidence"):
        result,trace=_conceptual(result,message,secrets_obj,s,budget,store)
        provider_ok=bool((trace or {}).get("ok")) if isinstance(trace,dict) else False
        if str((result.get("answer") or {}).get("mode") or "") in {"documented_answer","documented_answer_partial"} or provider_ok:
            result.setdefault("functional_events",[]).append({"type":"terminal_answer_arbitration","winner":"single_documented_composer","suppressed":"procedural_composer","reason":"documented_provider_completed" if provider_ok else "authorized_evidence_single_generation"})
            return result,trace,{"skipped":True,"reason":"documented_composer_is_terminal"}
    result,trace=maybe_generate_procedural(result,message,_gateway(secrets_obj,s),budget,store,_model_profile(secrets_obj).get("answer_model", ""))
    return result,{"skipped":True,"reason":"no_terminal_documented_answer"},trace

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
        store["memory"].last_assistant_question = context.get("closing_question") or None
        result["state_after"] = deepcopy(store["memory"].to_dict())


def _semantic_message(message):
    lines=[str(x).strip() for x in str(message or "").splitlines() if str(x).strip()]
    if len(lines)>1:
        ui_artifacts={"mostrar más líneas","mostrar mas lineas","show more lines"}
        lines=[line for index,line in enumerate(lines) if index==0 or line.casefold() not in ui_artifacts]
    return "\n".join(lines).strip()

def process_message(message, secrets_obj, s):
    original_message=str(message or "")
    message=_semantic_message(original_message)
    store = get_store(s)
    previous_budget=dict(store.get("budget") or {});expected_budget=BudgetPolicy.for_mode(str(previous_budget.get("mode") or "normal")).to_dict();budget_migrated=previous_budget!=expected_budget
    if budget_migrated:store["budget"]=expected_budget
    budget = BudgetPolicy(**store["budget"])
    memory_before = deepcopy(store["memory"])
    before = deepcopy(store["memory"].to_dict())
    key = _context_key(message, store["memory"])
    cached = store["exact_turn_cache"].get(key)
    execution = {"mode": budget.mode, "understanding_budget": budget.understanding_max_tokens, "response_budget": budget.response_max_tokens, "budget_migrated":budget_migrated, "previous_budget":previous_budget if budget_migrated else None, "model_profile": _model_profile(secrets_obj)}
    if cached:
        store["memory"].turn_number += 1
        result = {"input": original_message, "state_before": before, **deepcopy(cached["artifact"]), "state_after": deepcopy(store["memory"].to_dict()), "provider_trace": {"understanding": {"skipped": True, "reason": "exact_turn_cache"}, "response": {"skipped": True, "reason": "exact_turn_cache"}}, "execution": {**execution, "cache_hit": True}, "cache": {"hit": True, "type": "exact_turn"}, "production_changed": False}
        build_shadow_frame(store, message, result)
        result, conceptual, procedural = _answers(result, message, secrets_obj, s, budget, store)
        traces = _apply_answer_traces(result, conceptual, procedural, store)
        result["turn_metrics"] = _combined_turn_metrics([], traces)
        result = reconcile(result, store["memory"])
        result = normalize_generation_flags(result)
        _finalize_answer_context(result, store)
        # Commit the final documented context into the canonical topic registry.
        enrich_shadow_frame(store, result)
        refresh_shadow_diagnostics(result)
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
        result = _authorize_canonical_retrieval(result)
        build_shadow_frame(store, message, result)
        if (result.get("understanding") or {}).get("degraded"):
            store["memory"] = memory_before
            result["state_after"] = deepcopy(store["memory"].to_dict())
            result.setdefault("functional_events", []).append({"type": "degraded_understanding_memory_rollback", "reason": "provider_contract_invalid"})
        result = _attach_retrieval(result, message, store)
        # Persist the subject resolved from authorized evidence before the next turn.
        enrich_shadow_frame(store, result)
        refresh_shadow_diagnostics(result)
        base = result.get("provider_trace") or {}
        contract = (result.get("understanding_contract") or {}).get("valid")
        add_result(store["telemetry"], base.get("understanding"), contract)
        add_result(store["telemetry"], base.get("response"))
        result, conceptual, procedural = _answers(result, message, secrets_obj, s, budget, store)
        traces = _apply_answer_traces(result, conceptual, procedural, store)
        base_traces = [x for x in (base.get("understanding"), base.get("response")) if x and not x.get("skipped")]
        result["turn_metrics"] = _combined_turn_metrics(base_traces, traces)
        result = reconcile(result, store["memory"])
        result = normalize_generation_flags(result)
        _finalize_answer_context(result, store)
        # Commit the terminal answer and its evidence, not the temporary retrieval diagnostic.
        enrich_shadow_frame(store, result)
        refresh_shadow_diagnostics(result)
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
        result = {"input": original_message, "error": {"type": type(exc).__name__, "message": str(exc)}, "execution": execution, "production_changed": False}
    store["messages"].append({"role": "assistant", "content": text})
    store["turns"].append(result)
    return result

def export_session(s):
    x = get_store(s)
    return {"format": "agent_core_v2_clean_phase3c2_1_topic_evidence_continuity", "session_id": x.get("session_id"), "gateway_budget": {"calls": int(s.get("llm_gateway_calls", 0)), "tokens": int(s.get("llm_gateway_tokens", 0))}, "messages": deepcopy(x["messages"]), "turns": deepcopy(x["turns"]), "state": x["memory"].to_dict(), "answer_context": deepcopy(x.get("answer_context") or {}), "canonical_conversation_frame": deepcopy(x.get(CANONICAL_FRAME_KEY) or {}), "canonical_shadow_enabled": True, "canonical_topic_registry": deepcopy(x.get(CANONICAL_REGISTRY_KEY) or {}), "budget": deepcopy(x["budget"]), "telemetry": snapshot(x["telemetry"]), "cache_metrics": deepcopy(x["cache_metrics"]), "errors": deepcopy(x["errors"]), "retrieval_enabled": True, "documented_answer_enabled": True, "procedural_answer_enabled": True, "production_changed": False}



