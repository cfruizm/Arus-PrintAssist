# Agent Core V2 Clean - Phase 3C.5

## Objective
Case-conditioned evidence authority and broader generic retrieval without product-specific vocabulary.

## Changes
- Retains 3C.2 conceptual authority, 3C.3 pre-retrieval scope boundary, and 3C.4 diagnostic-to-procedural continuity.
- Adds a third generic retrieval attempt using only the canonical operation and subject, with top 10 recall.
- Removes stale support-case symptoms from unrelated procedural product queries.
- Suspends an active support case when an explicit independent subject replaces it.
- Requires active-case evidence to align with case/request terms and rejects unconfirmed mechanisms.
- Keeps detailed internal guidance but forbids undocumented exact UI labels, buttons, fields, URLs, services, and vendor values.
- Adds explicit resolved-case transition support.

## Validation
- Phase 3C.2 regression: 4 passed, 0 failed.
- Phase 3C.5: 9 passed, 0 failed.
- Compilation: passed.
- Generic policy modules checked for absence of benchmark product/feature vocabulary.
