from __future__ import annotations
from dataclasses import dataclass, asdict
import re

_CITE = re.compile(r"\[(R\d+)\]")
_SOURCE_LINE = re.compile(r"(?m)^\s*-\s*\[(R\d+)\].*$")

@dataclass(frozen=True)
class CitationAudit:
    cited_ids: list[str]
    valid_ids: list[str]
    remapped_ids: dict[str, str]
    unknown_ids: list[str]
    stripped_ids: list[str]
    valid: bool
    def to_dict(self): return asdict(self)


def finalize_citations(text: str, plan: dict | None) -> tuple[str, CitationAudit]:
    plan = plan or {}
    evidence = plan.get("evidence_plan") or {}
    response = plan.get("response_plan") or {}
    mapping = {str(k): str(v) for k, v in (evidence.get("citation_map") or {}).items()}
    valid = {str(x) for x in (evidence.get("documented_ids") or [])}
    allow = bool(response.get("allow_documented_claims"))
    source = str(text or "")
    cited_before = _CITE.findall(source)
    remapped = {cid: mapping[cid] for cid in cited_before if cid in mapping and mapping[cid] != cid}
    source = _CITE.sub(lambda m: f"[{mapping.get(m.group(1), m.group(1))}]", source)
    cited_after = _CITE.findall(source)
    unknown = sorted({cid for cid in cited_after if cid not in valid})
    stripped = []
    if not allow:
        stripped = sorted(set(cited_after))
        source = _CITE.sub("", source)
        source = _SOURCE_LINE.sub("", source)
        source = re.sub(r"(?m)^\s*\*\*Fuentes documentales\*\*\s*$", "", source)
        source = re.sub(r"\n{3,}", "\n\n", source).strip()
        unknown = []
    audit = CitationAudit(
        cited_ids=sorted(set(cited_after)),
        valid_ids=sorted(valid),
        remapped_ids=remapped,
        unknown_ids=unknown,
        stripped_ids=stripped,
        valid=(not unknown),
    )
    return source, audit


def enforce_answer_contract(payload: dict, canonical_plan: dict | None) -> tuple[dict, dict]:
    result = dict(payload or {})
    text, audit = finalize_citations(result.get("text", ""), canonical_plan)
    result["text"] = text
    plan_response = (canonical_plan or {}).get("response_plan") or {}
    allow_docs = bool(plan_response.get("allow_documented_claims"))
    internal = bool(result.get("internal_knowledge_used"))
    result["documented_evidence_used"] = allow_docs and bool(audit.cited_ids) and audit.valid
    if internal:
        result["knowledge_mode"] = "documented_plus_internal" if result["documented_evidence_used"] else "internal_only"
    elif result["documented_evidence_used"]:
        result["knowledge_mode"] = "documented_only"
    return result, audit.to_dict()
