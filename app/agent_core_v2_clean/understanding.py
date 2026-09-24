import json
from .contracts import UNDERSTANDING_SCHEMA
from .models import TurnUnderstanding
from .memory import compact_context, normalize_goal_updates

SYSTEM = """Semantic understanding for an enterprise printing-support assistant. Interpret the current message using memory only to resolve references. Return one complete JSON object. Distinguish social conversation, capability questions, conceptual, procedural, requirements, troubleshooting, architecture, warranty, cancellation and escalation. Do not infer intent from the previous goal when the current message is independent. current_goal may be a string or an object with summary, intent, known_details, missing_detail and status. conversation_act may be a string, list, composite label or object. Do not write markdown or commentary. Keep reasoning_summary under 20 words."""

REQUIRED = {"user_act", "intent", "topic_relation", "domain_relevance", "current_goal", "goal_complete", "goal_updates", "case_updates", "needs_clarification", "clarification_target", "should_retrieve", "confidence", "reasoning_summary"}
ALIASES = {"clarification_needed": "needs_clarification", "clarification_question": "clarification_target"}


def _text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, dict):
        for key in ("summary", "subject", "text", "value", "goal"):
            if value.get(key) not in (None, ""):
                return _text(value.get(key))
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(x for x in (_text(item) for item in value) if x)
    return str(value)


def _labels(value):
    out = []
    if isinstance(value, dict):
        for key, nested in value.items():
            out.extend(_labels(key))
            if nested not in ({}, [], None, ""):
                out.extend(_labels(nested))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            out.extend(_labels(item))
    else:
        text = str(value or "").strip().casefold()
        for separator in ("/", "|", ",", ";"):
            text = text.replace(separator, " ")
        out.extend(part for part in text.split() if part)
    return list(dict.fromkeys(out))


def _canonical_act(value):
    labels = set(_labels(value))
    if labels & {"request_capabilities", "capabilities", "capability", "capability_question", "assistant_capabilities", "meta"}:
        return "request_capabilities"
    if labels & {"acknowledgement", "acknowledgment", "social", "social_conversation", "greeting", "farewell", "thanks", "thank"}:
        return "social"
    if labels & {"answer_to_question", "answer"}:
        return "answer_to_question"
    if labels & {"request_elaboration", "elaboration"}:
        return "request_elaboration"
    if labels & {"reported_failure", "failure"}:
        return "reported_failure"
    if labels & {"attempt_result"}:
        return "attempt_result"
    if labels & {"topic_change", "change_topic"}:
        return "topic_change"
    if labels & {"cancel", "cancellation"}:
        return "cancel"
    if labels & {"escalation", "request_escalation"}:
        return "escalation"
    if labels & {"follow_up", "followup"}:
        return "follow_up"
    if labels & {"independent_question", "independent"}:
        return "independent_question"
    return "new_request"


def _canonical_intent(value, act, goal_intent=None):
    candidate = str(value or goal_intent or "unknown").strip().casefold()
    allowed = {"conceptual", "procedural", "troubleshooting", "requirements", "architecture", "warranty", "social", "cancel", "escalation", "unknown", "capabilities", "meta"}
    if act == "request_capabilities":
        return "capabilities"
    if act == "social":
        return "social"
    return candidate if candidate in allowed else "unknown"


class ConversationUnderstanding:
    def __init__(self, gateway, max_tokens=300):
        self.gateway = gateway
        self.max_tokens = max(160, min(650, int(max_tokens)))
        self.last_provider_result = {}
        self.contract_valid = False
        self.validation_error = None
        self.normalization = {"removed_goal_update_keys": []}

    def _degraded_current(self, message, reason):
        text = " ".join(str(message or "").split())
        return TurnUnderstanding("new_request", "unknown", "new_topic", "uncertain", text, False, {}, [], False, None, False, 0.0, reason, True)

    def _parse(self, text):
        value = str(text or "").strip()
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end < start:
            raise ValueError("json_object_missing")
        raw = json.loads(value[start:end + 1])
        if not isinstance(raw, dict) or not raw:
            raise ValueError("empty_object")

        aliases = {}
        for source, target in ALIASES.items():
            if target not in raw and source in raw:
                raw[target] = raw[source]
                aliases[source] = target

        conversation_act = raw.get("conversation_act", raw.get("user_act"))
        labels=set(_labels(conversation_act))
        if not raw.get("intent"):
            if labels & {"conceptual","definition","define"}:raw["intent"]="conceptual"
            elif labels & {"procedural","procedure","how_to","instructions","billing_distribution"}:raw["intent"]="procedural"
            elif labels & {"requirements","prerequisites","compatibility"}:raw["intent"]="requirements"
        act = _canonical_act(conversation_act)
        if "conversation_act" in raw:
            aliases["conversation_act"] = "user_act"

        goal = raw.get("current_goal")
        goal_intent = None
        goal_details = {}
        if isinstance(goal, dict):
            goal_intent = goal.get("intent")
            goal_details = goal.get("known_details") if isinstance(goal.get("known_details"), dict) else {}
            raw["current_goal"] = _text(goal.get("summary") or goal.get("subject") or goal.get("goal"))
            aliases["current_goal:object"] = "current_goal:string"
        else:
            raw["current_goal"] = _text(goal)

        updates = raw.get("goal_updates")
        if isinstance(updates, list):
            converted = {}
            for index, item in enumerate(updates):
                if isinstance(item, dict):
                    key = str(item.get("key") or item.get("type") or f"fact_{index + 1}")
                    val = _text(item.get("fact") or item.get("value"))
                    if val:
                        converted[key] = val
            updates = converted
            aliases["goal_updates:list"] = "goal_updates:dict"
        elif not isinstance(updates, dict):
            updates = {}
        updates = {**goal_details, **updates}

        raw["user_act"] = act
        raw["intent"] = _canonical_intent(raw.get("intent"), act, goal_intent)
        raw["goal_updates"] = updates
        raw.setdefault("topic_relation", "independent" if act in {"social", "request_capabilities"} else "new_topic")
        raw.setdefault("domain_relevance", "in_scope" if act in {"social", "request_capabilities"} else "uncertain")
        raw.setdefault("current_goal", "")
        raw.setdefault("goal_complete", False)
        raw.setdefault("case_updates", [])
        raw.setdefault("needs_clarification", False)
        raw.setdefault("clarification_target", None)
        raw.setdefault("should_retrieve", raw["intent"] not in {"social", "capabilities", "meta", "cancel"})
        raw.setdefault("confidence", 0.75)
        raw.setdefault("reasoning_summary", "provider_payload_normalized")
        if act in {"social", "request_capabilities"}:
            raw["should_retrieve"] = False
            raw["needs_clarification"] = False
            raw["clarification_target"] = None

        missing = REQUIRED - set(raw)
        if missing:
            raise ValueError("missing_fields:" + ",".join(sorted(missing)))
        allowed = set(REQUIRED)
        unknown = sorted(set(raw) - allowed)
        clean = {key: raw[key] for key in allowed}
        clean["current_goal"] = _text(clean.get("current_goal"))
        clean["goal_updates"], removed = normalize_goal_updates(clean.get("goal_updates"))
        clean["case_updates"] = [item for item in clean.get("case_updates") or [] if isinstance(item, dict)]
        self.normalization = {"removed_goal_update_keys": removed, "schema_aliases": aliases, "removed_unknown_fields": unknown, "contract_repaired": bool(aliases or unknown)}
        return TurnUnderstanding(**clean)

    def _normalize(self, understanding, memory):
        corrections = []
        if understanding.user_act == "answer_to_question" and not memory.last_assistant_question:
            understanding.user_act = "follow_up" if memory.active_topic else "new_request"
            corrections.append("answer_without_pending_question_normalized")
        if understanding.user_act == "request_elaboration" and not memory.active_topic and not memory.last_assistant_question:
            understanding.user_act = "new_request"
            understanding.topic_relation = "new_topic"
            corrections.append("orphan_elaboration_normalized")
        self.normalization.setdefault("structural_corrections", []).extend(corrections)
        return understanding

    def _request(self, payload, purpose, repair=False):
        from app.llm_gateway.models import LLMRequest
        instruction = SYSTEM if not repair else SYSTEM + " Repair the prior payload. Output one complete JSON object only."
        return self.gateway.complete(LLMRequest(
            [{"role": "system", "content": instruction}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}],
            purpose,
            420 if repair else self.max_tokens,
            0.0,
            UNDERSTANDING_SCHEMA,
            model_role="orchestrator",
            response_format_mode="text",
            reasoning_effort="low",
        ))

    def interpret(self, message, memory):
        first = self._request({"message": message, "context": compact_context(memory)}, "agent_core_v2_clean_understanding")
        self.last_provider_result = first.to_dict()
        self.contract_valid = False
        self.validation_error = None
        self.normalization = {"removed_goal_update_keys": []}
        if first.ok:
            try:
                parsed = self._parse(first.text)
                self.contract_valid = True
                return self._normalize(parsed, memory)
            except Exception as exc:
                first_error = str(exc)
        else:
            first_error = "provider_error:" + str(first.error_code or "unknown")

        retry = self._request({"message": message, "context": compact_context(memory), "invalid_output": str(first.text or "")[:3000], "validation_error": first_error}, "agent_core_v2_clean_understanding_repair", repair=True)
        self.last_provider_result = {"initial": first.to_dict(), "repair": retry.to_dict(), "repair_attempted": True}
        self.normalization = {"removed_goal_update_keys": [], "repair_attempted": True, "repair_succeeded": False}
        if retry.ok:
            try:
                parsed = self._parse(retry.text)
                self.contract_valid = True
                self.normalization["repair_succeeded"] = True
                return self._normalize(parsed, memory)
            except Exception as exc:
                self.validation_error = str(exc)
        else:
            self.validation_error = "repair_provider_error:" + str(retry.error_code or "unknown")
        return self._degraded_current(message, "invalid_understanding:" + str(self.validation_error or first_error))



