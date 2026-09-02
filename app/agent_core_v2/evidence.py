import html,re
from .models import EvidenceItem
def clean(v):return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",html.unescape(str(v or "")))).strip()
def words(v):return set(re.findall(r"[a-záéíóúñ0-9]{3,}",clean(v).casefold()))
INTENT_TERMS={"procedural":{"step","steps","procedure","configure","create","enable","pasos","procedimiento","configurar","crear","habilitar"},"troubleshooting":{"error","failed","issue","problem","troubleshoot","falla","problema","diagnóstico","diagnostico"},"requirements":{"requirement","requirements","supported","requisitos","compatible"},"conceptual":{"overview","introduction","what","concept","descripción","descripcion","introducción"}}
class EvidenceEngine:
 def __init__(self,retriever,min_eligible=.48,min_citable=.62):self.retriever=retriever;self.min_eligible=min_eligible;self.min_citable=min_citable
 def evaluate(self,query,decision,state,limit=8):
  raw=self.retriever(query,limit) or [];products={e.canonical_id for e in decision.entities if e.kind=="product"}|{e.canonical_id for e in state.active_topic.products};q=words(query);items=[];seen=set()
  for i,d in enumerate(raw,1):
   meta=dict(d.get("metadata") or {});h=str(meta.get("content_hash") or "");url=clean(d.get("url") or meta.get("source_url") or d.get("source"));key=h or url or clean(d.get("title"))
   if key in seen:continue
   seen.add(key);text=clean(d.get("text"));title=clean(d.get("title") or meta.get("title"));allw=words(title+" "+text);retr=float(d.get("score") or meta.get("score") or 0.5);doc_product=str(meta.get("product") or "").casefold();identity=1. if products and any(p.replace("_","") in doc_product.replace("_","") or doc_product.replace("_","") in p.replace("_","") for p in products) else (.5 if not products else 0.);topic=len(q&allw)/max(1,len(q));terms=INTENT_TERMS.get(decision.intent,set());intent=min(1.,len(terms&allw)/2);app=.30*min(1.,retr)+.30*identity+.25*min(1.,topic*3)+.15*intent;reasons=[]
   if identity==0:reasons.append("product_mismatch")
   if intent==0 and decision.intent in INTENT_TERMS:reasons.append("document_role_mismatch")
   eligible=app>=self.min_eligible and identity>0;citable=app>=self.min_citable and eligible and (intent>0 or topic>=.18)
   items.append(EvidenceItem(f"S{len(items)+1}",title,url,text,meta,retr,identity,intent,topic,round(app,3),eligible,citable,reasons))
  return {"retrieved":[x.to_dict() for x in items],"eligible":[x.to_dict() for x in items if x.eligible],"citable":[x.to_dict() for x in items if x.citable],"counts":{"retrieved":len(items),"eligible":sum(x.eligible for x in items),"citable":sum(x.citable for x in items)}}
