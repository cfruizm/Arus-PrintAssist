from __future__ import annotations
import statistics,time
from app.agent_core.models import RetrievedDocument
from app.integration.real_retrieval_bridge import LegacyRetrievalRunner
from app.retrieval.candidate_planner import build_plan,build_safe_filter

CONCEPTUAL_POSITIVE=("overview","introduction","introduccion","introducción","what is","que es","qué es","product overview","description","descripcion","descripción","purpose","proposito","propósito")
CONCEPTUAL_NEGATIVE=("subscription","renew","activating","sso","single sign-on","download","release history","release note","troubleshooting","configuration steps")

def source_key(doc):
    md=doc.metadata or {}; return str(md.get("canonical_url") or md.get("source_url") or md.get("source") or md.get("title") or "")
def canonical(value):return str(value or "").split("#",1)[0].rstrip("/")
def intent_adjustment(query_intent,doc):
    if query_intent!="conceptual":return 0.0
    md = doc.metadata or {}
    identity = " ".join([
        str(md.get("title", "")),
        str(md.get("document_family", "")),
        str(md.get("source_type", "")),
        str(doc.page_content or "")[:1200],
    ]).lower()
    return round((6.0 if any(t in identity for t in CONCEPTUAL_POSITIVE) else 0.0)+(-7.0 if any(t in identity for t in CONCEPTUAL_NEGATIVE) else 0.0),3)
def dedupe(items):
    out=[];seen=set()
    for doc,vector_score in items:
        key=canonical(source_key(doc)) or str(doc.page_content or "")[:160]
        if key in seen:continue
        seen.add(key);out.append((doc,vector_score))
    return out

def exact_documents(vectorstore,target):
    collection=vectorstore._collection; data=collection.get(include=["documents","metadatas"],limit=20000); output=[]
    for content,metadata in zip(data.get("documents",[]) or [],data.get("metadatas",[]) or []):
        metadata=metadata or {}; value=canonical(metadata.get("canonical_url") or metadata.get("source_url") or metadata.get("source"))
        if value==target: output.append((RetrievedDocument(str(content or ""),dict(metadata),1.0),1.0))
    return output

def candidate_once(query,vectorstore,metadata_counts,classify_intent,compute_rerank,top_k=6):
    plan=build_plan(query); query_intent=classify_intent(query); metadata_filter=build_safe_filter(plan,metadata_counts)
    if plan["exact_url"]: pairs=exact_documents(vectorstore,canonical(plan["exact_url"]))
    else:
        kwargs={"k":max(24,top_k*4)}
        if metadata_filter:kwargs["filter"]=metadata_filter
        try: raw=vectorstore.similarity_search_with_relevance_scores(query,**kwargs); pairs=[(RetrievedDocument(str(d.page_content or ""),dict(d.metadata or {}),float(score)),float(score)) for d,score in raw]
        except Exception:
            docs=vectorstore.as_retriever(search_kwargs=kwargs).invoke(query); pairs=[(RetrievedDocument(str(d.page_content or ""),dict(d.metadata or {}),0.0),0.0) for d in docs]
    scored=[]
    for neutral,vector_score in dedupe(pairs):
        proxy=type("DocumentProxy",(),{"page_content":neutral.page_content,"metadata":neutral.metadata})()
        backend_score=float(compute_rerank(query,proxy,query_intent)); adjustment=intent_adjustment(query_intent,neutral); final=backend_score+adjustment+(float(vector_score)*5.0)
        scored.append((neutral,{"vector_relevance":round(float(vector_score),4),"backend_rerank_score":round(backend_score,3),"intent_adjustment":adjustment,"final_score":round(final,3)}))
    scored.sort(key=lambda x:x[1]["final_score"],reverse=True)
    return {"plan":plan,"query_intent":query_intent,"metadata_filter":metadata_filter,"documents":scored[:top_k]}

def summarize_legacy(docs):
    return [{"rank":i,"title":d.metadata.get("title"),"source":source_key(d),"vendor":d.metadata.get("vendor"),"product":d.metadata.get("product"),"source_type":d.metadata.get("source_type"),"content_preview":d.page_content[:300]} for i,d in enumerate(docs,1)]
def summarize_candidate(scored):
    return [{"rank":i,"title":d.metadata.get("title"),"source":source_key(d),"vendor":d.metadata.get("vendor"),"product":d.metadata.get("product"),"source_type":d.metadata.get("source_type"),"scores":scores,"content_preview":d.page_content[:300]} for i,(d,scores) in enumerate(scored,1)]
def evaluate_query(query,retrieve_context,vectorstore,metadata_counts,classify_intent,compute_rerank,top_k=6,repetitions=2):
    legacy_runner=LegacyRetrievalRunner(retrieve_context); warmup=legacy_runner.warm_up(query); legacy=legacy_runner.run(query,top_k,repetitions)
    candidate_samples=[]; candidate=None
    for _ in range(max(1,repetitions)):
        started=time.perf_counter(); candidate=candidate_once(query,vectorstore,metadata_counts,classify_intent,compute_rerank,top_k); candidate_samples.append(time.perf_counter()-started)
    legacy_sources=[canonical(source_key(d)) for d in legacy["documents"] if source_key(d)]; candidate_sources=[canonical(source_key(d)) for d,_ in candidate["documents"] if source_key(d)]; left=set(legacy_sources[:3]);right=set(candidate_sources[:3])
    return {"query":query,"warmup_seconds":warmup,"plan":candidate["plan"],"query_intent":candidate["query_intent"],"metadata_filter":candidate["metadata_filter"],"legacy":{"median_latency_seconds":legacy["median_latency_seconds"],"latency_samples":legacy["latency_samples"],"documents":summarize_legacy(legacy["documents"])},"candidate":{"median_latency_seconds":round(statistics.median(candidate_samples),4),"latency_samples":[round(v,4) for v in candidate_samples],"documents":summarize_candidate(candidate["documents"])},"metrics":{"top1_match":bool(legacy_sources and candidate_sources and legacy_sources[0]==candidate_sources[0]),"top3_overlap":round(len(left&right)/max(1,len(left|right)),4),"exact_source_respected":all(s==canonical(candidate["plan"]["exact_url"]) for s in candidate_sources) if candidate["plan"]["exact_url"] else None},"llm_calls":0}
