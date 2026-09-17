from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _dedupe(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = _norm(value)
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            out.append(clean)
    return out


@dataclass(frozen=True)
class ConfirmedContext:
    observations: tuple[str, ...]
    attempts: tuple[tuple[str, str], ...]
    affected_scope: str | None
    confirmed_facts: tuple[tuple[str, str], ...]

    def to_prompt_block(self) -> str:
        lines = ["CONTEXTO CONFIRMADO DEL CASO:"]
        if self.affected_scope:
            lines.append(f"- Alcance confirmado: {self.affected_scope}")
        for value in self.observations:
            lines.append(f"- Observacion confirmada: {value}")
        for action, result in self.attempts:
            lines.append(f"- Accion ya realizada: {action}")
            if result:
                lines.append(f"  Resultado confirmado: {result}")
        for key, value in self.confirmed_facts:
            lines.append(f"- Hecho confirmado ({key}): {value}")
        lines.extend([
            "REGLAS OBLIGATORIAS:",
            "- No contradigas ningun hecho confirmado.",
            "- No recomiendes de nuevo una accion ya realizada, salvo que expliques por que debe repetirse de forma distinta.",
            "- No recomiendes una modalidad incompatible con el alcance confirmado.",
            "- Indica brevemente que ya quedo razonablemente descartado.",
            "- Propone el siguiente paso con mayor poder de discriminacion y que sea reversible.",
        ])
        return "\n".join(lines)


def build_confirmed_context(result: dict[str, Any]) -> ConfirmedContext:
    state = result.get("state_after") or result.get("state") or {}
    case = state.get("support_case") or {}
    contract = result.get("response_contract") or {}
    observations = _dedupe(case.get("observations") or [])
    attempts: list[tuple[str, str]] = []
    for item in case.get("attempts") or []:
        action = _norm((item or {}).get("action"))
        outcome = _norm((item or {}).get("result"))
        if action:
            attempts.append((action, outcome))
    facts: list[tuple[str, str]] = []
    for item in contract.get("confirmed_facts") or []:
        key = _norm((item or {}).get("key"))
        value = _norm((item or {}).get("value"))
        if key and value:
            facts.append((key, value))
    return ConfirmedContext(
        observations=tuple(observations),
        attempts=tuple(attempts),
        affected_scope=_norm(case.get("affected_scope")) or None,
        confirmed_facts=tuple(facts),
    )


def enrich_internal_request(payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload or {})
    context = build_confirmed_context(result)
    enriched["confirmed_case_context"] = {
        "observations": list(context.observations),
        "attempts": [{"action": a, "result": r} for a, r in context.attempts],
        "affected_scope": context.affected_scope,
        "confirmed_facts": [{"key": k, "value": v} for k, v in context.confirmed_facts],
    }
    enriched["confirmed_case_prompt"] = context.to_prompt_block()
    return enriched
