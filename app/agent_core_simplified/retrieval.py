from __future__ import annotations
import re
def clean(v):return re.sub(r"\s+"," ",str(v or "")).strip()
def display(e):
 name=clean(getattr(e,"name","") or getattr(e,"mention","") or getattr(e,"canonical_id",""));return clean(getattr(e,"mention","")) if "_" in name and getattr(e,"mention","") else name.replace("_"," ").title()
def build_query(message,state,plan):
 parts=[];products=[display(x) for x in state.active_topic.products]
 if products:parts.append("Product: "+", ".join(products))
 if state.case.symptoms:parts.append("Issue or need: "+"; ".join(state.case.symptoms))
 if state.case.affected_scope:parts.append("Affected scope: "+state.case.affected_scope)
 for d in state.case.details[-4:]:parts.append(str(d.get("type"))+": "+str(d.get("value")))
 failed=[x.action for x in state.case.attempts if x.result]
 if failed:parts.append("Do not repeat completed unsuccessful actions: "+"; ".join(failed))
 parts.append("Current request: "+clean(message));parts.append("Request type: "+plan.request_kind)
 return ". ".join(parts)+"."
def prepare_candidates(raw,limit=5):
 out=[];seen=set()
 for d in raw or []:
  m=dict(d.get("metadata") or {});key=str(m.get("content_hash") or d.get("url") or m.get("source_url") or d.get("title"))
  if not key or key in seen:continue
  seen.add(key);out.append({"id":f"S{len(out)+1}","title":clean(d.get("title") or m.get("title")),"url":clean(d.get("url") or m.get("source_url") or d.get("source")),"excerpt":clean(d.get("text"))[:1200],"metadata":{"product":m.get("product"),"component":m.get("component"),"document_family":m.get("document_family"),"source_type":m.get("source_type")}})
  if len(out)>=limit:break
 return out
