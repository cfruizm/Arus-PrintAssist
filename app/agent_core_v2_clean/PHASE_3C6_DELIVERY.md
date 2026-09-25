# Agent Core V2 Clean - Phase 3C.6

## Objective
Recover documents requested by explicit identifier before semantic retrieval can dilute the identifier with conversational context.

## Root cause addressed
The complete user query repeated the identifier inside a long semantic request. Vector retrieval returned a semantically nearby but incorrect document. The runtime had no deterministic identifier-first retrieval lane and therefore never inspected the correct document.

## Generic correction
- Detect structured document identifiers using a format pattern, not a list of known IDs.
- Generate normalized compact, dashed, underscored, spaced, and full-title query variants.
- Retrieve each variant with expanded recall.
- Verify the identifier against title, source path, URL, source_name, or metadata title.
- Only exact identifier matches enter the exact-document route.
- Expand the matched source to recover its ordered pages.
- Preserve the normal semantic route when no identifier is present or no exact match exists.

No named product, document, feature, or benchmark identifier is embedded in the policy.
