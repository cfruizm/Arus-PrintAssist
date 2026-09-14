from __future__ import annotations
from copy import deepcopy
import hashlib

def _stable_id(item):
    meta=item.get("metadata") or {}
    payload="|".join(str(x or "") for x in (meta.get("content_hash"),meta.get("canonical_url"),item.get("source"),item.get("url"),item.get("page"),item.get("text")))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

def register_evidence(items):
    """Assign citation IDs once, after final selection, and preserve provenance."""
    selected=[]; mapping={}; seen=set()
    for item in items or []:
        stable=_stable_id(item)
        if stable in seen: continue
        seen.add(stable); row=deepcopy(item); rid=f"R{len(selected)+1}"; old=str(row.get("id") or "")
        row.update({"id":rid,"stable_id":stable,"original_id":old or None});selected.append(row);mapping[stable]=rid
        if old: mapping[old]=rid
    return selected,mapping

def citation_plan(items):
    selected,mapping=register_evidence(items)
    return {"selected_evidence":selected,"citation_map":mapping,"valid_ids":[x["id"] for x in selected]}
