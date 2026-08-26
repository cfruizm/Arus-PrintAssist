from dataclasses import dataclass, field
from typing import Any
@dataclass
class RetrievedDocument:
    page_content: str
    metadata: dict[str,Any]
    score: float = 0.0
@dataclass
class ShadowResult:
    query: str
    detected_products: list[str] = field(default_factory=list)
    detected_processes: list[str] = field(default_factory=list)
    legacy_sources: list[str] = field(default_factory=list)
    candidate_sources: list[str] = field(default_factory=list)
    top1_match: bool = False
    top3_overlap: float = 0.0
    exact_source_respected: bool | None = None
    legacy_error: str | None = None
    candidate_error: str | None = None
    llm_calls: int = 0
