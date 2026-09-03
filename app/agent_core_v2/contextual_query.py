from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Any

DETAIL_PREFIXES = {
    "timeline": "Momento o periodo informado",
    "change_context": "Cambios recientes informados",
    "environment": "Entorno informado",
    "error_message": "Mensaje de error",
    "technical_context": "Contexto técnico adicional",
}
MAX_DETAIL_ITEMS = 4
MAX_QUERY_CHARS = 1400


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _display_name(entity: Any) -> str:
    name = _clean(getattr(entity, "canonical_name", ""))
    matched = _clean(getattr(entity, "matched_text", ""))
    candidate = name or matched
    if candidate and "_" not in candidate:
        return candidate
    if matched:
        return matched
    return candidate.replace("_", " ").strip().title()


def _parse_detail(value: str) -> tuple[str, str]:
    raw = _clean(value)
    if ":" not in raw:
        return "technical_context", raw
    kind, content = raw.split(":", 1)
    kind = _clean(kind).casefold()
    return (kind if kind in DETAIL_PREFIXES else "technical_context", _clean(content))


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean(value)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


@dataclass
class ContextualRetrievalQuery:
    original_query: str
    contextual_query: str
    fields_used: dict[str, list[str]]
    fields_omitted: dict[str, list[str]]
    failed_actions_excluded: list[str]
    product_display_names: list[str]
    query_chars: int

    def to_dict(self) -> dict:
        return asdict(self)


class ContextualRetrievalQueryBuilder:
    """Build a retrieval request from the canonical state, without product rules."""

    def __init__(self, max_query_chars: int = MAX_QUERY_CHARS):
        self.max_query_chars = max(500, min(2200, int(max_query_chars)))

    def build(self, message: str, decision: Any, state: Any) -> ContextualRetrievalQuery:
        products = _unique([_display_name(item) for item in state.active_topic.products])
        components = _unique([_display_name(item) for item in state.active_topic.components])
        processes = _unique([_display_name(item) for item in state.active_topic.processes])
        symptoms = _unique(list(state.technical_case.symptoms or []))
        scope = _clean(state.technical_case.affected_scope)

        attempted: list[str] = []
        failed: list[str] = []
        successful: list[str] = []
        for item in state.technical_case.attempts or []:
            action = _clean(getattr(item, "action", ""))
            result = _clean(getattr(item, "result", "")).casefold()
            if not action:
                continue
            attempted.append(action)
            if result in {"failed", "failure", "unresolved", "fallido", "no_resuelto"}:
                failed.append(action)
            elif result in {"resolved", "successful", "success", "exitoso"}:
                successful.append(action)

        details: list[str] = []
        omitted_details: list[str] = []
        for raw_detail in state.technical_case.evidence or []:
            kind, content = _parse_detail(raw_detail)
            if not content:
                continue
            formatted = f"{DETAIL_PREFIXES[kind]}: {content}"
            if len(details) < MAX_DETAIL_ITEMS:
                details.append(formatted)
            else:
                omitted_details.append(formatted)

        sections: list[str] = []
        if products:
            sections.append("Producto o solución: " + ", ".join(products))
        if components:
            sections.append("Componente confirmado: " + ", ".join(components))
        if processes:
            sections.append("Proceso solicitado: " + ", ".join(processes))
        if symptoms:
            sections.append("Síntoma o necesidad: " + "; ".join(symptoms))
        if scope:
            sections.append("Alcance afectado: " + scope)
        sections.extend(details)
        if failed:
            sections.append("No repetir estas acciones porque ya fallaron: " + "; ".join(_unique(failed)))
        if successful:
            sections.append("Acciones que ya resultaron exitosas: " + "; ".join(_unique(successful)))
        sections.append("Solicitud actual: " + _clean(message))
        sections.append("Objetivo documental: " + self._intent_objective(str(decision.intent)))

        contextual = ". ".join(section.rstrip(".") for section in sections if section) + "."
        omitted_for_length: list[str] = []
        if len(contextual) > self.max_query_chars:
            # Preserve product, symptom, failed actions and current request. Drop older details first.
            reduced = [section for section in sections if not any(section.startswith(prefix) for prefix in DETAIL_PREFIXES.values())]
            omitted_for_length = details
            contextual = ". ".join(section.rstrip(".") for section in reduced if section) + "."
            contextual = contextual[: self.max_query_chars].rstrip(" .") + "."

        return ContextualRetrievalQuery(
            original_query=_clean(message),
            contextual_query=contextual,
            fields_used={
                "products": products,
                "components": components,
                "processes": processes,
                "symptoms": symptoms,
                "affected_scope": [scope] if scope else [],
                "case_details": details,
                "attempted_actions": _unique(attempted),
            },
            fields_omitted={
                "extra_case_details": omitted_details,
                "length_reduction": omitted_for_length,
            },
            failed_actions_excluded=_unique(failed),
            product_display_names=products,
            query_chars=len(contextual),
        )

    @staticmethod
    def _intent_objective(intent: str) -> str:
        return {
            "troubleshooting": "encontrar la siguiente validación aplicable al caso activo",
            "procedural": "encontrar pasos documentados para la operación solicitada",
            "requirements": "encontrar requisitos y dependencias explícitamente documentados",
            "architecture": "encontrar información documentada de arquitectura y componentes",
            "warranty": "encontrar condiciones documentadas de garantía",
            "conceptual": "encontrar una explicación documentada y específica",
        }.get(intent, "encontrar información directamente aplicable a la solicitud")


def build_case_detail_acknowledgement(state: Any, new_facts: list[dict]) -> str:
    products = _unique([_display_name(item) for item in state.active_topic.products])
    product = ", ".join(products) or "el caso activo"
    details: list[str] = []
    for fact in new_facts or []:
        kind = str(fact.get("type") or "")
        value = _clean(fact.get("value"))
        if not value:
            continue
        if kind == "timeline":
            details.append("el momento informado")
        elif kind == "change_context":
            details.append("la ausencia de cambios conocidos")
        elif kind == "affected_scope":
            details.append("el alcance afectado")
        elif kind == "error_message":
            details.append("el mensaje de error")
        else:
            details.append("el detalle adicional")
    detail_text = ", ".join(_unique(details)) or "la información adicional"
    return f"Entendido. Registré {detail_text} para {product} y lo conservaré para la siguiente validación."
