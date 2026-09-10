from __future__ import annotations
import copy, hashlib, re, unicodedata

VERSION = "semantic_evidence_fit_v3_modifier_alignment"
STOP = {"para","como","que","del","las","los","una","uno","con","por","sin","antes","debo","debe","deben","en","el","la","y","o","how","what","the","and","for","from","with","this","that","before","after","into","using","is","are","to","configure","configurar","explicar","realizar","aplicar","revisar","necesito","quiero"}
# Canonical concepts are language bridges, not product or benchmark rules.
CONCEPTS = {
 "authentication":{"autenticacion","authenticate","authentication","credential","credentials","credencial","credenciales","login","identity","identidad","access","acceso"},
 "validation":{"validar","validacion","verify","verification","check","checking","confirm","comprobar","revisar","prerequisite","requirement","requirements","requisito","requisitos"},
 "printing":{"impresion","imprimir","print","printing","printer","impresora","job","trabajo","spooler"},
 "tracking":{"tracking","rastreo","seguimiento","monitoreo","monitoring","registro","log"},
 "security":{"segura","seguro","seguridad","secure","security","protection","proteccion"},
 "user":{"usuario","usuarios","user","users","account","accounts","cuenta","cuentas"},
 "device":{"dispositivo","dispositivos","device","devices","mfd","mfp","equipo","equipos"},
 "cost":{"cost","costes","costo","costos","gasto","gastos","expense","expenses"},
 "configuration":{"configuracion","configure","configured","configuration","setting","settings","ajuste","ajustes"},
}

def _norm(value):
 value=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode().casefold()
 return " ".join(re.findall(r"[a-z0-9_-]{2,}",value))

def _raw_terms(value):return {x for x in _norm(value).split() if x not in STOP and len(x)>=3}
def _terms(value):
 raw=_raw_terms(value);out=set(raw)
 for concept,variants in CONCEPTS.items():
  if raw & variants:out.add("concept:"+concept)
 return out

def _identity(item):return str(item.get("url") or item.get("source") or (item.get("metadata") or {}).get("canonical_url") or item.get("title") or "")
def _document_terms(item):
 meta=item.get("metadata") or {}
 return _terms(" ".join(str(x or "") for x in (item.get("title"),item.get("text"),meta.get("product"),meta.get("component"),meta.get("document_family"),meta.get("source_group"))))
def _specificity(item):
 meta=item.get("metadata") or {};title=_raw_terms(item.get("title"));return {"product":str(meta.get("product") or "").casefold(),"component":str(meta.get("component") or "").casefold(),"title_terms":title}
def _group_key(item):return _identity(item) or str(item.get("title") or "")

def evaluate_item(item,query_text,fields=None,answer_context=None):
 fields=fields or {};answer_context=answer_context or {};details=fields.get("details") or {}
 stable=" ".join(str(x or "") for x in (query_text,fields.get("goal"),fields.get("contextual_operation"),fields.get("current_message")," ".join(str(v) for v in details.values())))
 q=_terms(stable);d=_document_terms(item);title_terms=_terms(item.get("title"));overlap=q&d;title_overlap=q&title_terms
 concept_q={x for x in q if x.startswith("concept:")};concept_match=concept_q&d
 coverage=len(overlap)/max(1,len(q));title_coverage=len(title_overlap)/max(1,len(q));concept_coverage=len(concept_match)/max(1,len(concept_q)) if concept_q else 0.0
 previous_ids=set(answer_context.get("source_identities") or []);follow=fields.get("user_act") in {"follow_up","answer_to_question","attempt_result","reported_failure"};continuity=0.20 if follow and _identity(item) in previous_ids else 0.0
 specific=_specificity(item);confirmed=" ".join(str(v).casefold() for v in details.values());product= specific["product"]
 product_bonus=0.12 if product and any(part and part in confirmed for part in re.split(r"[_\s-]+",product)) else 0.0
 # Penalize scope-heavy titles only when their distinctive terms are neither in the query nor in the previous answer context.
 prior_terms=_terms(answer_context.get("main_text_excerpt") or "");distinct={x for x in specific["title_terms"] if not x.startswith("concept:")} - {x for x in q if not x.startswith("concept:")} - {x for x in prior_terms if not x.startswith("concept:")}
 query_concepts={x for x in q if x.startswith("concept:")};document_concepts={x for x in d if x.startswith("concept:")};unrequested_concepts=document_concepts-query_concepts
 modifier_penalty=min(0.32,0.16*len(unrequested_concepts))
 penalty=min(0.24,0.035*len(distinct))+modifier_penalty
 score=max(0.0,min(1.0,0.42*coverage+0.22*title_coverage+0.24*concept_coverage+continuity+product_bonus-penalty))
 return {"score":round(score,4),"query_terms":sorted(q),"matched_terms":sorted(overlap),"title_matched_terms":sorted(title_overlap),"concept_matches":sorted(concept_match),"unconfirmed_title_terms":sorted(distinct)[:12],"continuity_boost":continuity,"product_context_bonus":product_bonus,"unrequested_concepts":sorted(unrequested_concepts),"modifier_penalty":round(modifier_penalty,4),"assumption_penalty":round(penalty,4)}

def _prior_evidence(answer_context):
 out=[]
 for item in answer_context.get("cited_evidence") or []:
  row=copy.deepcopy(item);row["carried_from_previous_answer"]=True;out.append(row)
 return out

def apply_semantic_fit(retrieval,answer_context=None):
 result=copy.deepcopy(retrieval or {});query=result.get("query") or {};fields=query.get("fields") or {};follow=fields.get("user_act") in {"follow_up","answer_to_question","attempt_result","reported_failure"}
 evidence=list(result.get("evidence") or [])
 if follow:
  known={_identity(x) for x in evidence}
  for old in _prior_evidence(answer_context or {}):
   if _identity(old) not in known:evidence.append(old);known.add(_identity(old))
 ranked=[]
 for pos,item in enumerate(evidence):
  row=copy.deepcopy(item);fit=evaluate_item(row,query.get("text") or "",fields,answer_context or {});row["semantic_fit"]=fit;ranked.append((fit["score"],-pos,row))
 ranked.sort(reverse=True,key=lambda x:(x[0],x[1]));ordered=[x[2] for x in ranked]
 groups={}
 for row in ordered:groups.setdefault(_group_key(row),[]).append(row)
 group_scores=[]
 for key,items in groups.items():
  scores=sorted((x["semantic_fit"]["score"] for x in items),reverse=True);group_scores.append((round(0.72*scores[0]+0.28*(sum(scores[:3])/max(1,min(3,len(scores)))),4),key,items))
 group_scores.sort(reverse=True,key=lambda x:x[0]);selected_group=group_scores[0] if group_scores else (0.0,"",[])
 # Isolate generation evidence from diagnostic candidates. Generators must not mix documents accidentally.
 diagnostic=ordered
 generation=selected_group[2]
 result["diagnostic_evidence"]=diagnostic
 result["generation_evidence"]=generation
 result["evidence"]=generation
 best=selected_group[0];prior_quality=float(((result.get("selection") or {}).get("quality") or 0.0));combined=round(max(0.0,min(1.0,0.76*best+0.24*prior_quality)),4)
 result.setdefault("selection",{})["quality"]=combined
 result["semantic_fit"]={"version":VERSION,"best_group_score":best,"combined_quality":combined,"selected_document":selected_group[1],"selected_group_ids":[str(x.get("id")) for x in selected_group[2]],"carried_previous_evidence":sum(1 for x in evidence if x.get("carried_from_previous_answer")),"previous_answer_sources_used":bool(follow and answer_context and answer_context.get("source_identities")),"accepted_for_generation":combined>=0.38,"low_fit":combined<0.38,"ranked_ids":[str(x.get("id")) for x in diagnostic],"generation_ids":[str(x.get("id")) for x in generation],"diagnostic_count":len(diagnostic),"generation_count":len(generation)}
 return result

def capture_answer_context(result):
 answer=result.get("answer") or {};retrieval=result.get("retrieval") or {};text=str(answer.get("text") or "").strip()
 if not text:return {}
 cited=set(re.findall(r"\[(R\d+)\]",text));evidence=retrieval.get("evidence") or [];chosen=[e for e in evidence if not cited or str(e.get("id")) in cited]
 identities=[];titles=[];compact=[]
 for item in chosen[:6]:
  identity=_identity(item)
  if identity and identity not in identities:identities.append(identity)
  title=str(item.get("title") or "").strip()
  if title and title not in titles:titles.append(title)
  compact.append({"id":item.get("id"),"title":title,"source":item.get("source"),"url":item.get("url"),"page":item.get("page"),"text":" ".join(str(item.get("text") or "").split())[:1000],"metadata":{k:v for k,v in (item.get("metadata") or {}).items() if k in {"product","component","document_family","canonical_url","source_group"}}})
 return {"answer_mode":answer.get("mode"),"goal":(result.get("understanding") or {}).get("current_goal"),"main_text_excerpt":" ".join(text.split())[:1000],"source_identities":identities,"source_titles":titles,"cited_ids":sorted(cited),"cited_evidence":compact,"finish_reason":answer.get("finish_reason"),"partial":str(answer.get("mode") or "").endswith("_partial") or str(answer.get("finish_reason") or "").casefold() in {"length","max_tokens"}}
