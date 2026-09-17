from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

_METHOD_RE = re.compile(r"(?:^|\n)\s*(?:\d+[.)]\s*)?(?P<title>[^\n]{2,80})\s*(?:\n|$)", re.I)


def _clean(text: Any) -> str:
    return " ".join(str(text or "").replace("\x00", " ").split()).strip()


def _identity(item: dict[str, Any]) -> str:
    meta = item.get("metadata") or {}
    return _clean(item.get("source") or item.get("url") or meta.get("canonical_url") or item.get("title"))


def infer_evidence_scope(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    manufacturers: list[str] = []
    products: list[str] = []
    tools: list[str] = []
    for item in evidence:
        meta = item.get("metadata") or {}
        vendor = _clean(meta.get("vendor"))
        product = _clean(meta.get("product"))
        title = _clean(item.get("title"))
        if vendor and vendor.casefold() not in {"unknown", "general", "arus_internal"}:
            manufacturers.append(vendor)
        if product and product.casefold() not in {"unknown", "general", "sanitized_support_assets"}:
            products.append(product)
        if title:
            tools.append(title)
    return {
        "manufacturers": list(dict.fromkeys(manufacturers)),
        "products": list(dict.fromkeys(products)),
        "document_titles": list(dict.fromkeys(tools)),
        "specific": bool(manufacturers or products),
    }


def _method_name(item: dict[str, Any]) -> str:
    text = _clean(item.get("text"))
    # Structural extraction only: names come from document headings, never from a fixed product vocabulary.
    for raw_line in str(item.get("text") or "").splitlines():
        line = _clean(raw_line).strip("-:.;")
        if 2 <= len(line) <= 70 and (re.match(r"^\d+[.)]\s*", line) or line.isupper()):
            return re.sub(r"^\d+[.)]\s*", "", line).strip()
    return "Procedimiento documentado"


def build_structured_fallback(evidence: list[dict[str, Any]], request_scope: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence = [dict(x) for x in (evidence or []) if _clean((x or {}).get("text"))]
    scope = infer_evidence_scope(evidence)
    branches: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for item in evidence:
        name = _method_name(item)
        branches.setdefault(name, []).append(item)
    sections: list[str] = ["**Procedimiento documentado**"]
    if scope["specific"] and not any((request_scope or {}).get(k) for k in ("manufacturer", "product", "model")):
        covered = ", ".join(scope["manufacturers"] + scope["products"] + scope["document_titles"][:1])
        sections.append(f"> Alcance: la evidencia disponible corresponde a {covered}. No debe asumirse aplicable a otros fabricantes o modelos.")
    used: list[str] = []
    for index, (name, items) in enumerate(branches.items(), 1):
        sections.append(f"\n**Metodo {index}: {name}**")
        step_index = 1
        for item in items:
            text = _clean(item.get("text"))
            if not text:
                continue
            cid = _clean(item.get("id"))
            citation = f" [{cid}]" if cid else ""
            sections.append(f"{step_index}. {text}{citation}")
            step_index += 1
            if cid:
                used.append(cid)
    return {
        "text": "\n".join(sections),
        "used_evidence_ids": list(dict.fromkeys(used)),
        "branch_count": len(branches),
        "evidence_scope": scope,
        "requires_scope_detail": scope["specific"] and not any((request_scope or {}).get(k) for k in ("manufacturer", "product", "model")),
    }
