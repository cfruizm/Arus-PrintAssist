# Agent Core V2 Clean - Phase 3C.7

## Objective
Preserve exact-document authority across follow-up requests while preventing evidence from a previous product from becoming the answer after an explicit subject change.

## Corrections
- Exact document retrieval expands with the current follow-up operation, not only with the document identifier.
- Same-document expansion can keep up to 24 relevant chunks instead of silently truncating every exact document to 8.
- Request-shell language such as asking to provide or show a documented procedure is not treated as the requested technical operation.
- Exact document evidence can authorize a procedural answer when the matched source contains ordered operational content.
- An explicit subject change is classified as changed scope before referential continuity, so previous evidence is comparison-only and removed from generation.
- Generic policies contain no product, feature, or benchmark document names.
