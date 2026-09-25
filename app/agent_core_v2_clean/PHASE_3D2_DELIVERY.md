# Agent Core V2 Clean - Phase 3D.2

## Purpose
Close the documental consolidation stage by communicating evidence limitations accurately without weakening grounding.

## Limitation taxonomy
- `document_not_found`: identifier is absent from the metadata catalog.
- `document_ambiguous`: multiple documents match the identifier.
- `document_found_operational_evidence_insufficient`: the exact document and fragments exist, but do not support the requested operation strongly enough.
- `evidence_found_not_authorized`: related fragments exist, but authority rejects them.
- `evidence_partial`: documentation supports only part of the requested answer.
- `provider_degraded`: evidence exists, but provider execution failed or truncated.
- `no_evidence_retrieved`: retrieval returned no useful fragments.

## Preserved behavior
- Deterministic document resolver over runtime vector-store metadata.
- Semantic retrieval for requests without identifiers.
- Corrected-source reconciliation and negative constraints.
- Strict grounding for procedural answers.
- 720-token procedural response budget and preventive gateway rollover.

## Checkpoints
- Preserve `agent-core-v2-clean-3b4.1-stable` as the rollback checkpoint.
- If the 3D.2 acceptance campaign passes, create `agent-core-v2-clean-3d2-documental-stable`.

## Next stage
Phase 4A should implement modular escalation, including field collection, confirmation, correction, cancellation, clean exit, structured export, and loop prevention.
