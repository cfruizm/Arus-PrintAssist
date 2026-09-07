from __future__ import annotations

STRICT_EVIDENCE_POLICY = """Evaluate whether each EXCERPT, not merely its document title, supports the exact current request.
Rules:
1. direct requires that the excerpt itself contains the requested answer or concrete values/steps/conditions.
2. A document title or introduction saying that the document covers the subject is not enough for direct support.
3. If the excerpt concerns the same product but a different task, classify not_applicable or contextual as appropriate.
4. For numeric specifications, compatibility lists, procedures, or prerequisites, supported_claims must preserve every explicit item visible in the excerpt that answers the request.
5. Return one assessment for every supplied source id, including not_applicable sources. Never omit an id.
6. Keep reason under 25 words and supported_claims concise.
"""

def prepend_strict_policy(existing_system_prompt: str) -> str:
    return STRICT_EVIDENCE_POLICY + "\n" + str(existing_system_prompt or "")
