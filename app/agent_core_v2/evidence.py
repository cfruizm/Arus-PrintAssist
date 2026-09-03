from __future__ import annotations
import html,re
from .models import EvidenceItem
def clean(v):return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",html.unescape(str(v or "")))).strip()
def words(v):return set(re.findall(r"[a-záéíóúñ0-9]{3,}",clean(v).casefold()))
ROLE_TERMS={"procedural":{"step","steps","procedure","configure","create","enable","assign","pasos","procedimiento","configurar","crear","habilitar","asignar"},"troubleshooting":{"error","failed","issue","problem","troubleshoot","missing","disappear","tracked","falla","problema","diagnóstico","desaparece"},"requirements":{"requirement","requirements","supported","requisitos","compatible"},"conceptual":{"overview","introduction","what","concept","descripción","introducción"}}
class ProductCompatibility:
 def __init__(self,registry=None):self.registry=registry
 def compatible(self,expected,document,title=""):
  if not expected:return .5
  doc=str(document or "").casefold();normalized=lambda x:str(x).casefold().replace("_","").replace("-","")
  if any(normalized(x)==normalized(doc) for x in expected):return 1.
  if self.registry:
   fn=getattr(self.registry,"are_document_products_compatible",None)
   if callable(fn) and any(fn(x,document) for x in expected):return 1.
   rel=getattr(self.registry,"DOCUMENT_PRODUCT_COMPATIBILITY",{})
   if isinstance(rel,dict) and any(doc in {str(v).casefold() for v in rel.get(x,[])} for x in expected):return 1.
  # Title may explicitly name multiple editions. Generic and reusable, no product IDs embedded.
  titlew=words(title)
  if doc and any(set(str(x).casefold().replace("_"," ").split())<=titlew for x in expected):return .85
  return 0.
class EvidenceEngine:
 def __init__(self,retriever,min_eligible=.48,min_citable=.66,compatibility=None):self.retriever=retriever;self.min_eligible=min_eligible;self.min_citable=min_citable;self.compatibility=compatibility or ProductCompatibility()
 def evaluate(self,query,decision,state,limit=8):
  raw=self.retriever(query,limit) or [];expected={e.canonical_id for e in decision.entities if e.kind=="product"}|{e.canonical_id for e in state.active_topic.products};q=words(query);items=[];seen=set();terms=ROLE_TERMS.get(decision.intent,set())
  for d in raw:
   meta=dict(d.get("metadata") or {});url=clean(d.get("url") or meta.get("source_url") or d.get("source"));title=clean(d.get("title") or meta.get("title"));key=str(meta.get("content_hash") or url or title)
   if key in seen:continue
   seen.add(key);text=clean(d.get("text"));allw=words(title+" "+text);retr=float(d.get("score") or meta.get("score") or .5);identity=self.compatibility.compatible(expected,meta.get("product"),title);overlap=len(q&allw)/max(1,len(q));intent=min(1.,len(terms&allw)/2) if terms else .5;app=.25*min(1.,retr)+.30*identity+.30*min(1.,overlap*3)+.15*intent;reasons=[]
   if identity==0:reasons.append("product_mismatch")
   if decision.intent in ROLE_TERMS and intent==0:reasons.append("document_role_mismatch")
   if overlap<.12:reasons.append("low_topic_alignment")
   eligible=identity>0 and app>=self.min_eligible
   citable=eligible and app>=self.min_citable and intent>0 and overlap>=.12 and not reasons
   items.append(EvidenceItem(f"S{len(items)+1}",title,url,text,meta,retr,identity,intent,overlap,round(app,3),eligible,citable,reasons))
  return {"retrieved":[x.to_dict() for x in items],"eligible":[x.to_dict() for x in items if x.eligible],"citable":[x.to_dict() for x in items if x.citable],"counts":{"retrieved":len(items),"eligible":sum(x.eligible for x in items),"citable":sum(x.citable for x in items)}}
