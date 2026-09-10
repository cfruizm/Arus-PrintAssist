from __future__ import annotations
import copy,re,unicodedata
VERSION="semantic_evidence_fit_v5_open_lexical_baseline"

def _norm(v):return " ".join(re.findall(r"[a-z0-9_-]{3,}",unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold()))
def _terms(v):return set(_norm(v).split())
def _identity(x):return str(x.get("url") or x.get("source") or (x.get("metadata") or {}).get("canonical_url") or x.get("title") or "")
def _group_key(x):return _identity(x) or str(x.get("title") or "")
def evaluate_item(item,query_text,fields=None,answer_context=None):
 fields=fields or {};answer_context=answer_context or {};details=fields.get("details") or {}
 query=" ".join(str(x or "") for x in (query_text,fields.get("goal"),fields.get("contextual_operation"),fields.get("current_message")," ".join(map(str,details.values()))))
 document=" ".join(str(x or "") for x in (item.get("title"),item.get("text"),(item.get("metadata") or {}).get("product"),(item.get("metadata") or {}).get("component")))
 q=_terms(query);d=_terms(document);title=_terms(item.get("title"));overlap=q&d
 lexical=len(overlap)/max(1,len(q));title_overlap=q&title;title_score=len(title_overlap)/max(1,len(q))
 follow=fields.get("user_act") in {"follow_up","answer_to_question","attempt_result","reported_failure"};continuity=.18 if follow and _identity(item) in set(answer_context.get("source_identities") or []) else 0.
 score=max(0.,min(1.,.74*lexical+.18*title_score+continuity))
 return {"score":round(score,4),"query_terms":sorted(q),"matched_terms":sorted(overlap),"title_matched_terms":sorted(title_overlap),"continuity_boost":continuity,"scoring_basis":"open_lexical_overlap_no_domain_dictionary"}
def _prior(ctx):
 out=[]
 for item in (ctx or {}).get("cited_evidence") or []:row=copy.deepcopy(item);row["carried_from_previous_answer"]=True;out.append(row)
 return out
def apply_semantic_fit(retrieval,answer_context=None):
 result=copy.deepcopy(retrieval or {});query=result.get("query") or {};fields=query.get("fields") or {};follow=fields.get("user_act") in {"follow_up","answer_to_question","attempt_result","reported_failure"};evidence=list(result.get("evidence") or [])
 if follow:
  known={_identity(x) for x in evidence}
  for old in _prior(answer_context):
   if _identity(old) not in known:evidence.append(old);known.add(_identity(old))
 ranked=[]
 for pos,item in enumerate(evidence):row=copy.deepcopy(item);fit=evaluate_item(row,query.get("text") or "",fields,answer_context or {});row["semantic_fit"]=fit;ranked.append((fit["score"],-pos,row))
 ranked.sort(reverse=True,key=lambda x:(x[0],x[1]));ordered=[x[2] for x in ranked];groups={}
 for row in ordered:groups.setdefault(_group_key(row),[]).append(row)
 scores=[]
 for key,items in groups.items():
  vals=sorted((x["semantic_fit"]["score"] for x in items),reverse=True);scores.append((round(.72*vals[0]+.28*(sum(vals[:3])/max(1,min(3,len(vals)))),4),key,items))
 scores.sort(reverse=True,key=lambda x:x[0]);selected=scores[0] if scores else (0.,"",[]);generation=selected[2];best=selected[0];prior_quality=float((result.get("selection") or {}).get("quality") or 0.);combined=round(max(0.,min(1.,.76*best+.24*prior_quality)),4)
 result["diagnostic_evidence"]=ordered;result["generation_evidence"]=generation;result["evidence"]=generation;result.setdefault("selection",{})["quality"]=combined
 result["evidence_scope"]={"coverage":"candidate","selected_document":selected[1],"specificity_not_inferred_lexically":True}
 result["semantic_fit"]={"version":VERSION,"best_group_score":best,"combined_quality":combined,"selected_document":selected[1],"selected_group_ids":[str(x.get("id")) for x in generation],"carried_previous_evidence":sum(1 for x in evidence if x.get("carried_from_previous_answer")),"previous_answer_sources_used":bool(follow and answer_context and answer_context.get("source_identities")),"accepted_for_generation":combined>=.38,"low_fit":combined<.38,"ranked_ids":[str(x.get("id")) for x in ordered],"generation_ids":[str(x.get("id")) for x in generation],"diagnostic_count":len(ordered),"generation_count":len(generation),"closed_vocabularies":False}
 return result
def capture_answer_context(result):
 answer=result.get("answer") or {};retrieval=result.get("retrieval") or {};text=str(answer.get("text") or "").strip()
 if not text:return {}
 cited=set(re.findall(r"\[(R\d+)\]",text));chosen=[e for e in retrieval.get("evidence") or [] if not cited or str(e.get("id")) in cited];ids=[];titles=[];compact=[]
 for item in chosen[:6]:
  identity=_identity(item);title=str(item.get("title") or "").strip()
  if identity and identity not in ids:ids.append(identity)
  if title and title not in titles:titles.append(title)
  compact.append({"id":item.get("id"),"title":title,"source":item.get("source"),"url":item.get("url"),"page":item.get("page"),"text":" ".join(str(item.get("text") or "").split())[:1000],"metadata":{k:v for k,v in (item.get("metadata") or {}).items() if k in {"product","component","document_family","canonical_url","source_group"}}})
 return {"answer_mode":answer.get("mode"),"goal":(result.get("understanding") or {}).get("current_goal"),"main_text_excerpt":" ".join(text.split())[:1000],"source_identities":ids,"source_titles":titles,"cited_ids":sorted(cited),"cited_evidence":compact,"finish_reason":answer.get("finish_reason"),"partial":str(answer.get("mode") or "").endswith("_partial") or str(answer.get("finish_reason") or "").casefold() in {"length","max_tokens"}}
