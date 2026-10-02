from __future__ import annotations
import re

_CONDITIONAL_MARKERS=(
    "si el entorno", "si la configuración", "si el controlador", "si los trabajos",
    "si aplica", "en caso de que", "cuando el entorno", "if the environment",
    "if the configuration", "if the driver", "if the jobs", "if applicable",
)
_DIRECT_STEP_PATTERNS=(
    r"\bel siguiente paso(?: documentado)? es\b",
    r"\bla siguiente acción(?: documentada)? es\b",
    r"\besta acción es necesaria\b",
    r"\bthe next documented step is\b",
    r"\bthe next step is\b",
    r"\bthis action is required\b",
)

def guard_unconfirmed_applicability(text):
    """Remove a universal lead when the same answer later states its prerequisites.

    This is deliberately domain-neutral. It does not infer missing conditions or rewrite
    procedures. It only suppresses a contradictory introductory paragraph and leaves the
    cited conditional explanation intact.
    """
    value=str(text or "").strip()
    paragraphs=[x.strip() for x in re.split(r"\n\s*\n",value) if x.strip()]
    if len(paragraphs)<2:
        return value,False,{"reason":"insufficient_structure"}
    later=" ".join(paragraphs[1:]).casefold()
    has_condition=any(marker in later for marker in _CONDITIONAL_MARKERS)
    lead=paragraphs[0].casefold()
    direct=any(re.search(pattern,lead,re.I) for pattern in _DIRECT_STEP_PATTERNS)
    if not (has_condition and direct):
        return value,False,{"reason":"no_universal_conditional_conflict","condition_detected":has_condition,"direct_lead_detected":direct}
    repaired="\n\n".join(paragraphs[1:]).strip()
    return repaired,True,{"reason":"universal_lead_removed_before_conditional_guidance","condition_detected":True,"direct_lead_detected":True}
