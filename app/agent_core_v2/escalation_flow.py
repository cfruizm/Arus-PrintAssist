from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class EscalationField:
    key: str
    question: str
    fact_types: tuple[str, ...] = ()

# Native, product-independent escalation contract. It consumes canonical case state,
# not product names, keyword lists or a copied V1 backend workflow.
FIELDS = (
    EscalationField("issue_description", "Describe brevemente el problema que debe escalarse.", ("symptom", "error_message", "observed_behavior")),
    EscalationField("impact_scope", "¿Cuál es el alcance o impacto del problema, por ejemplo un usuario, varios usuarios o todo el servicio?", ("affected_scope",)),
    EscalationField("troubleshooting_performed", "¿Qué validaciones o acciones se realizaron y qué resultado tuvieron?", ("attempted_action", "attempt_result")),
)

class NativeEscalationCoordinator:
    def start(self, state) -> None:
        state.escalation.status = "collecting"
        state.escalation.suspended_reason = None
        self.sync_from_case(state)
        self._advance(state)

    def continue_flow(self, state, message: str, facts: list[dict[str, Any]] | None = None) -> None:
        self.sync_from_case(state)
        pending = state.escalation.pending_field
        value = " ".join(str(message or "").split())
        # While a field is pending, the current answer belongs to that field. This is
        # contextual capture, not phrase matching and works for any product/language.
        if pending and value and pending not in state.escalation.collected_fields:
            state.escalation.collected_fields[pending] = value
        self._capture_facts(state, facts or [])
        self.sync_from_case(state)
        self._advance(state)

    def sync_from_case(self, state) -> None:
        fields = state.escalation.collected_fields
        case = state.technical_case
        if case.symptoms and "issue_description" not in fields:
            fields["issue_description"] = "; ".join(case.symptoms)
        if case.affected_scope and "impact_scope" not in fields:
            fields["impact_scope"] = str(case.affected_scope)
        if case.attempts and "troubleshooting_performed" not in fields:
            values=[]
            for attempt in case.attempts:
                text=str(attempt.action)
                if attempt.result: text += f" (resultado: {attempt.result})"
                values.append(text)
            fields["troubleshooting_performed"] = "; ".join(values)

    def _capture_facts(self, state, facts: list[dict[str, Any]]) -> None:
        by_type={}
        for fact in facts:
            kind=str(fact.get("type") or "")
            value=" ".join(str(fact.get("value") or "").split())
            if kind and value: by_type.setdefault(kind,[]).append(value)
        for field in FIELDS:
            values=[v for kind in field.fact_types for v in by_type.get(kind,[])]
            if values: state.escalation.collected_fields[field.key]="; ".join(values)

    def _advance(self, state) -> None:
        missing=next((field for field in FIELDS if not state.escalation.collected_fields.get(field.key)),None)
        if missing:
            state.escalation.status="collecting"
            state.escalation.pending_field=missing.key
        else:
            state.escalation.status="ready"
            state.escalation.pending_field=None

    @staticmethod
    def question_for(pending_field: str | None) -> str | None:
        field=next((x for x in FIELDS if x.key==pending_field),None)
        return field.question if field else None

    @staticmethod
    def summary(state) -> str:
        values=state.escalation.collected_fields
        lines=["El escalamiento quedó preparado con la información recopilada:"]
        labels={"issue_description":"Problema","impact_scope":"Impacto","troubleshooting_performed":"Validaciones realizadas"}
        for field in FIELDS:
            if values.get(field.key): lines.append(f"- **{labels[field.key]}:** {values[field.key]}")
        lines.append("Puedes revisar este resumen antes de enviarlo por el mecanismo de escalamiento disponible.")
        return "\n".join(lines)
