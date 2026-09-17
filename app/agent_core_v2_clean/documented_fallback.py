from __future__ import annotations

from collections import OrderedDict
import re
from typing import Any, Iterable

_NON_OPERATIONAL_MARKERS = (
    "aviso legal", "informacion de uso interno", "información de uso interno",
    "informacion restringida", "información restringida", "control de registros",
    "control de cambios", "responsable", "definiciones", "anexos",
)
_ACTION_MARKERS = (
    "agregar", "seleccionar", "ingresar", "digitar", "identificar", "crear",
    "usar", "hacer clic", "clic", "desactivar", "retirar", "reemplazar",
    "remplazar", "asignar", "colocar", "finalizar", "instalar", "abrir",
    "indicar", "confirmar", "buscar", "elegir", "configurar", "seleccion", "ruta", "controlador",
)


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _page_number(item: dict[str, Any]) -> int:
    raw = item.get("page") or (item.get("metadata") or {}).get("page_label")
    match = re.search(r"\d+", str(raw or ""))
    return int(match.group()) if match else 10**9


def _identity(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") or {}
    return _norm(metadata.get("canonical_url") or item.get("url") or item.get("source") or item.get("title"))


def _title(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") or {}
    return _norm(item.get("title") or metadata.get("title") or metadata.get("source_name") or "Documento")


def _remove_headers(text: str) -> str:
    text = _norm(text)
    text = re.sub(r"^DA\d[^•]*?(?=(?:CONTENIDO|\d+\.|•))", "", text, flags=re.I)
    text = re.sub(r"\b(?:OBJETIVO|ALCANCE)\b.*?(?=(?:CONTENIDO|\d+\.|•))", "", text, flags=re.I)
    return _norm(text)


def _is_non_operational(text: str) -> bool:
    folded = text.casefold()
    if any(marker in folded for marker in _NON_OPERATIONAL_MARKERS):
        return True
    return not any(marker in folded for marker in _ACTION_MARKERS)


def _extract_actions(text: Any) -> list[str]:
    cleaned = _remove_headers(str(text or ""))
    if not cleaned or _is_non_operational(cleaned):
        return []
    pieces = re.split(r"\s*•\s*|(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ])", cleaned)
    actions: list[str] = []
    for piece in pieces:
        piece = _norm(piece).strip(" .;:-")
        if not piece or _is_non_operational(piece):
            continue
        if len(piece) > 360:
            action_pos = min((piece.casefold().find(k) for k in _ACTION_MARKERS if k in piece.casefold()), default=-1)
            if action_pos >= 0:
                piece = piece[action_pos:]
        if 8 <= len(piece) <= 360:
            actions.append(piece[0].upper() + piece[1:])
    return actions


def _compress_pages(pages: Iterable[int]) -> str:
    values = sorted({p for p in pages if p < 10**9})
    if not values:
        return ""
    ranges: list[tuple[int, int]] = []
    start = previous = values[0]
    for page in values[1:]:
        if page == previous + 1:
            previous = page
            continue
        ranges.append((start, previous)); start = previous = page
    ranges.append((start, previous))
    labels = [str(a) if a == b else f"{a} a {b}" for a, b in ranges]
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " y " + labels[-1]


def _merge_short_actions(actions: list[tuple[str, str]]) -> list[tuple[str, list[str]]]:
    merged: list[tuple[str, list[str]]] = []
    for text, citation in actions:
        if merged and len(text) < 45:
            previous_text, previous_citations = merged[-1]
            merged[-1] = (previous_text.rstrip(".") + ". " + text, list(dict.fromkeys(previous_citations + [citation])))
        else:
            merged.append((text, [citation]))
    return merged


def build_documented_fallback(retrieval: dict[str, Any] | None, reason: str = "provider_degraded") -> dict[str, Any] | None:
    retrieval = retrieval or {}
    evidence = list(retrieval.get("generation_evidence") or retrieval.get("evidence") or [])
    evidence.sort(key=lambda item: (_identity(item), _page_number(item), str(item.get("id") or "")))

    actions: list[tuple[str, str]] = []
    documents: OrderedDict[str, dict[str, Any]] = OrderedDict()
    used_ids: list[str] = []
    for item in evidence:
        citation = _norm(item.get("id"))
        if not citation:
            continue
        extracted = _extract_actions(item.get("text"))
        if not extracted:
            continue
        identity = _identity(item)
        document = documents.setdefault(identity, {"title": _title(item), "pages": set()})
        page = _page_number(item)
        if page < 10**9:
            document["pages"].add(page)
        for action in extracted:
            actions.append((action, citation))
        used_ids.append(citation)

    if not actions:
        return None

    steps = []
    for index, (text, citations) in enumerate(_merge_short_actions(actions), start=1):
        citation_text = " ".join(f"[{citation}]" for citation in citations)
        steps.append(f"{index}. {text} {citation_text}")

    source_lines = []
    for document in documents.values():
        page_range = _compress_pages(document["pages"])
        suffix = f", páginas {page_range}" if page_range and (" a " in page_range or "," in page_range or " y " in page_range) else (f", página {page_range}" if page_range else "")
        source_lines.append(f"- {document['title']}{suffix}")

    text = "**Procedimiento documentado**\n\n" + "\n".join(steps)
    text += "\n\n**Fuentes documentales**\n" + "\n".join(source_lines)
    normalized_reason = "provider_output_truncated" if reason in {"length", "incomplete_generation_length"} else reason
    return {
        "text": text,
        "mode": "procedural_documented_fallback",
        "knowledge_used": True,
        "provider": None,
        "model": None,
        "usage": {},
        "finish_reason": "deterministic_fallback",
        "documented_evidence_used": True,
        "internal_knowledge_used": False,
        "knowledge_mode": "documented_only",
        "degraded": True,
        "degraded_reason": normalized_reason,
        "fallback_diagnostics": {
            "source_document_count": len(documents),
            "used_evidence_ids": list(dict.fromkeys(used_ids)),
            "discarded_evidence_count": len(evidence) - len(set(used_ids)),
        },
    }
