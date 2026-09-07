"""Integration helper for app/agent_core_v2/interpreter.py.

In QwenInterpreter.interpret, immediately after parsing `raw` and before `_normalize(raw, state)`, add:

    from .semantic_reconciler import contract_is_suspicious, repair_contract
    if contract_is_suspicious(raw):
        repaired, repair_trace = repair_contract(self.gateway, message, state, raw)
        self.last_trace["contract_repair"] = repair_trace
        if repaired is not None:
            raw = {**raw, **repaired}

Also replace the interpreter system prompt with CURRENT_TURN_SYSTEM_PROMPT below.
"""

CURRENT_TURN_SYSTEM_PROMPT = """Interpret only the current user turn. Use canonical state only to resolve omitted products, objects, or references. Classify intent independently from the previous turn: conceptual asks what something is or its purpose; procedural asks how to perform an action; requirements asks prerequisites, compatibility, capacity, or dependencies; troubleshooting reports a failure or seeks diagnosis; architecture asks design or integration. Every clear technical need is conversation_act=technical_request and requires_documents=true. Do not use clarification merely because details could improve the answer. Use clarification only when the technical need itself cannot be determined. Return compact JSON and keep reasoning_summary under 25 words."""
