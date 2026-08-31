from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Any
import inspect

@dataclass
class RetrievedEvidence:
    text:str
    title:str=""
    source:str=""
    url:str=""
    score:float|None=None
    metadata:dict|None=None
    def to_dict(self):return asdict(self)

def _read(item:Any,name:str,default=None):
    if isinstance(item,dict):return item.get(name,default)
    return getattr(item,name,default)

def _normalize_item(item:Any)->RetrievedEvidence:
    metadata=_read(item,"metadata",{}) or {}
    if not isinstance(metadata,dict):metadata={}
    text=_read(item,"page_content",None) or _read(item,"text",None) or _read(item,"content",None) or _read(item,"document",None) or ""
    title=_read(item,"title",None) or metadata.get("title") or metadata.get("name") or ""
    source=_read(item,"source",None) or metadata.get("source") or metadata.get("file") or ""
    url=_read(item,"url",None) or metadata.get("url") or metadata.get("source_url") or ""
    score=_read(item,"score",None)
    if score is None:score=_read(item,"relevance_score",None)
    try:score=None if score is None else float(score)
    except Exception:score=None
    return RetrievedEvidence(str(text or "")[:12000],str(title or "")[:500],str(source or "")[:1000],str(url or "")[:2000],score,metadata)

def _invoke(fn,query,k):
    signature=inspect.signature(fn);params=signature.parameters
    kwargs={}
    if "query" in params:kwargs["query"]=query
    elif "user_query" in params:kwargs["user_query"]=query
    elif "question" in params:kwargs["question"]=query
    if "k" in params:kwargs["k"]=k
    elif "top_k" in params:kwargs["top_k"]=k
    elif "limit" in params:kwargs["limit"]=k
    if kwargs:return fn(**kwargs)
    return fn(query)

def retrieve_from_existing_backend(query:str,k:int=6)->dict:
    """Read-only adapter. It never calls generate_answer_with_rag or an LLM."""
    import app.backend as backend
    candidates=("retrieve_and_rerank","retrieve_relevant_documents","retrieve_documents","search_documents","semantic_search","search_knowledge_base")
    errors=[]
    for name in candidates:
        fn=getattr(backend,name,None)
        if not callable(fn):continue
        try:
            raw=_invoke(fn,query,k)
            if isinstance(raw,tuple):raw=raw[0]
            if isinstance(raw,dict):raw=raw.get("documents") or raw.get("results") or raw.get("items") or []
            evidence=[_normalize_item(item) for item in list(raw or [])[:k]]
            evidence=[item for item in evidence if item.text.strip()]
            return {"ok":True,"adapter":name,"query":query,"evidence":[item.to_dict() for item in evidence],"count":len(evidence),"errors":errors}
        except Exception as exc:errors.append(f"{name}:{type(exc).__name__}:{exc}")
    return {"ok":False,"adapter":None,"query":query,"evidence":[],"count":0,"errors":errors,"error_code":"compatible_retriever_not_found"}
