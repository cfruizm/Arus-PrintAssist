# Agent Core V2 Clean - Phase 3D.1

## Purpose
Replace vector-only document-code lookup with deterministic resolution against the metadata already present in the configured vector store.

## Architectural behavior
1. Extract normalized document identifiers from the current request, active goal and subject.
2. Build a cached in-memory catalog from vector-store metadata.
3. Resolve zero, one or multiple documents by exact normalized identity.
4. Retrieve chunks only from the uniquely resolved source.
5. Keep semantic vector retrieval for requests without a document identifier.

## Preserved controls
- Corrected source preserves the prior conversational operation.
- Negative user constraints remove incompatible evidence.
- Weak content-only procedural matches are not authorized.
- Documented procedural output budget remains 720 tokens.
- Gateway windows roll over preventively while cumulative metrics remain visible.

## No overfitting
The production resolver contains no campaign document code, product name or benchmark question. The catalog is generated dynamically from metadata at runtime.
