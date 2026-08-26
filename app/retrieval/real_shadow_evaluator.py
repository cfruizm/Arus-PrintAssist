from __future__ import annotations
import statistics,time
from app.agent_core.models import RetrievedDocument
from app.integration.real_retrieval_bridge import LegacyRetrievalRunner
from app.retrieval.candidate_planner import build_plan,build_filter
from app.retrieval.scope_policy import classify_document_role

def source_key(doc):
    md=doc.metadata or {};return str(md.get("canonical_url") or md.get("source_url") or md.get("source") or md.get("title") or "")
def canonical(value):return str(value or "").split("#",1)[0].rstrip("/")
def proxy(doc):return type("DocumentProxy",(),{"page_content":doc.page_content,"metadata":doc.metadata})()
def dedupe(docs):
    out=[];seen=set()
    for doc in docs:
        key=canonical(source_key(doc)) or doc.page_content[:160]
        if key in seen:continue
        seen.add(key);out.append(doc)
    return out
def exact_docs(vectorstore,target):
    data=vectorstore._collection.get(include=["documents","metadatas"],limit=20000);out=[]
    for content,md in zip(data.get("documents",[]) or [],data.get("metadatas",[]) or []):
        md=md or {}
        if canonical(md.get("canonical_url") or md.get("source_url") or md.get("source"))==target:out.append(RetrievedDocument(str(content or ""),dict(md),0.0))
    return out
def filtered_docs(vectorstore,query,metadata_filter,k):
    kwargs={"k":max(30,k*5)}
    if metadata_filter:kwargs["filter"]=metadata_filter
    return [RetrievedDocument(str(d.page_content or ""),dict(d.metadata or {}),0.0) for d in vectorstore.as_retriever(search_kwargs=kwargs).invoke(query)]
def candidate_once(query,retrieve_context,vectorstore,counts,classify_intent,compute_rerank,top_k):
    intent=classify_intent(query);plan=build_plan(query,intent);policy=plan["scope_policy"];metadata_filter=build_filter(plan,counts)
    if plan["exact_url"]:docs=exact_docs(vectorstore,canonical(plan["exact_url"]))
    elif policy["filter_policy"]=="shared_family":
        # Reuse the proven expanded/anchor candidate generation, then apply the new external policy.
        _,raw=retrieve_context(query,top_k=max(top_k,8));docs=[RetrievedDocument(str(d.page_content or ""),dict(d.metadata or {}),0.0) for d in raw]
    else:docs=filtered_docs(vectorstore,query,metadata_filter,top_k)
    scored=[]
    for vector_rank,doc in enumerate(dedupe(docs),1):
        title=str((doc.metadata or {}).get("title","") or "");source_type=str((doc.metadata or {}).get("source_type","") or "")
        role,role_score,reasons=classify_document_role(title,source_type,intent);backend=float(compute_rerank(query,proxy(doc),intent));rank_score=max(0.0,7.0-(vector_rank-1));final=backend+role_score+rank_score
        scored.append((doc,{"vector_rank":vector_rank,"vector_rank_score":rank_score,"backend_rerank_score":round(backend,3),"intent_role":role,"intent_role_score":role_score,"reasons":reasons,"final_score":round(final,3)}))
    scored.sort(key=lambda x:x[1]["final_score"],reverse=True)
    aligned=sum(1 for _,s in scored[:top_k] if s["intent_role"]=="intent_aligned")
    intent_supported=aligned>0
    if policy.get("sparse_collection") and intent=="conceptual" and not intent_supported:intent_supported=False
    return {"plan":plan,"query_intent":intent,"metadata_filter":metadata_filter,"documents":scored[:top_k],"intent_supported":intent_supported,"support_reason":"At least one editorially aligned source was found." if intent_supported else "No editorially aligned source was found for the requested intent."}
def summarize_legacy(docs):return [{"rank":i,"title":d.metadata.get("title"),"source":source_key(d),"vendor":d.metadata.get("vendor"),"product":d.metadata.get("product"),"source_type":d.metadata.get("source_type"),"content_preview":d.page_content[:300]} for i,d in enumerate(docs,1)]
def summarize_candidate(items):return [{"rank":i,"title":d.metadata.get("title"),"source":source_key(d),"vendor":d.metadata.get("vendor"),"product":d.metadata.get("product"),"source_type":d.metadata.get("source_type"),"scoring":s,"content_preview":d.page_content[:300]} for i,(d,s) in enumerate(items,1)]
def evaluate_query(query,retrieve_context,vectorstore,counts,classify_intent,compute_rerank,top_k=6,repetitions=2):
    runner=LegacyRetrievalRunner(retrieve_context);warmup=runner.warm_up(query);legacy=runner.run(query,top_k,repetitions);samples=[];candidate=None
    for _ in range(max(1,repetitions)):
        started=time.perf_counter();candidate=candidate_once(query,retrieve_context,vectorstore,counts,classify_intent,compute_rerank,top_k);samples.append(time.perf_counter()-started)
    legacy_sources=[canonical(source_key(d)) for d in legacy["documents"] if source_key(d)];candidate_sources=[canonical(source_key(d)) for d,_ in candidate["documents"] if source_key(d)];left=set(legacy_sources[:3]);right=set(candidate_sources[:3])
    return {"query":query,"warmup_seconds":warmup,"plan":candidate["plan"],"query_intent":candidate["query_intent"],"metadata_filter":candidate["metadata_filter"],"intent_supported":candidate["intent_supported"],"support_reason":candidate["support_reason"],"legacy":{"median_latency_seconds":legacy["median_latency_seconds"],"latency_samples":legacy["latency_samples"],"documents":summarize_legacy(legacy["documents"])},"candidate":{"median_latency_seconds":round(statistics.median(samples),4),"latency_samples":[round(v,4) for v in samples],"documents":summarize_candidate(candidate["documents"])},"metrics":{"top1_match":bool(legacy_sources and candidate_sources and legacy_sources[0]==candidate_sources[0]),"top3_overlap":round(len(left&right)/max(1,len(left|right)),4),"exact_source_respected":all(s==canonical(candidate["plan"]["exact_url"]) for s in candidate_sources) if candidate["plan"]["exact_url"] else None},"llm_calls":0}
