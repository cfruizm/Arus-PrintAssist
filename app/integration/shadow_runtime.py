from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from app.integration.feature_flags import AGENT_CORE_V1_SHADOW_ENABLED, AGENT_CORE_V1_SHADOW_WRITE_REPORT
from app.retrieval.shadow_compare import compare_retrieval

class ShadowRuntime:
    def __init__(self, legacy_callable, candidate_callable, report_path: str | Path):
        self.legacy_callable = legacy_callable
        self.candidate_callable = candidate_callable
        self.report_path = Path(report_path)

    def evaluate(self, query: str) -> dict:
        if not AGENT_CORE_V1_SHADOW_ENABLED:
            return {"status": "disabled", "llm_calls": 0}
        result = compare_retrieval(query, self.legacy_callable, self.candidate_callable)
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), **asdict(result), "status": "evaluated"}
        if AGENT_CORE_V1_SHADOW_WRITE_REPORT:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            with self.report_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
