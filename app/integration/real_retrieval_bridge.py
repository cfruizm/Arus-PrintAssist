from __future__ import annotations
import statistics
import time
from typing import Callable

from app.agent_core.models import RetrievedDocument


def convert_documents(items) -> list[RetrievedDocument]:
    output=[]
    for item in items or []:
        output.append(RetrievedDocument(
            str(getattr(item,"page_content","") or ""),
            dict(getattr(item,"metadata",{}) or {}),
            float((getattr(item,"metadata",{}) or {}).get("_score",0.0) or 0.0),
        ))
    return output


class LegacyRetrievalRunner:
    def __init__(self,retrieve_context_callable:Callable):
        self.retrieve_context=retrieve_context_callable

    def warm_up(self,query:str)->float:
        started=time.perf_counter()
        self.retrieve_context(query,top_k=1)
        return round(time.perf_counter()-started,4)

    def run(self,query:str,top_k:int=6,repetitions:int=2)->dict:
        samples=[]; last_context=""; last_docs=[]
        for _ in range(max(1,repetitions)):
            started=time.perf_counter(); last_context,last_docs=self.retrieve_context(query,top_k=top_k); samples.append(time.perf_counter()-started)
        return {
            "documents":convert_documents(last_docs),
            "context_chars":len(str(last_context or "")),
            "latency_samples":[round(v,4) for v in samples],
            "median_latency_seconds":round(statistics.median(samples),4),
            "llm_calls":0,
        }
