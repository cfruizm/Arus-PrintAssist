from __future__ import annotations
import hashlib,json,re,unicodedata
from .models import AgentResponse
from .answer_context_policy import enrich_internal_payload
PROMPT_VERSION="controlled_internal_knowledge_v11_authorized_evidence"
WARNING="⚠️ **Orientación complementaria basada en conocimiento general del modelo**"
SYSTEM="""Actúa como colega de soporte empresarial de impresión. Usa exactamente: ### Lo que indica la documentación, ### Orientación complementaria, ### Antes de continuar. La primera sección solo usa extractos autorizados y citas [R#]. Las otras secciones no usan citas. Respeta hechos confirmados. No conviertas modalidades sugeridas en hechos. Formula como máximo una pregunta indispensable. No menciones procesos internos. Máximo 220 palabras."""
def _norm(v):return ''.join(c for c in unicodedata.normalize('NFKD',str(v or '').casefold()) if not unicodedata.combining(c))
def _terms(v):return set(re.findall(r'[a-z0-9]{3,}',_norm(v)))
def _stable(e):return hashlib.sha256(json.dumps([e.get('url') or e.get('source'),e.get('page')," ".join(str(e.get('text') or '').split())],ensure_ascii=False).encode()).hexdigest()[:16]
def authorized_evidence(retrieval,max_items=6,max_chars=5200):
 source=list(retrieval.get('generation_evidence') or retrieval.get('evidence') or []);source+=list(((retrieval.get('_answer_context') or {}).get('cited_evidence') or []));out=[];seen=set();used=0
 for e in source:
  sid=_stable(e)
  if sid in seen:continue
  seen.add(sid);row={'id':f'R{len(out)+1}','stable_id':sid,'title':e.get('title'),'page':e.get('page'),'text':" ".join(str(e.get('text') or '').split())[:1300],'origin':'previous_answer' if e.get('carried_from_previous_answer') or e in ((retrieval.get('_answer_context') or {}).get('cited_evidence') or []) else 'current_turn'};n=len(json.dumps(row,ensure_ascii=False))
  if out and used+n>max_chars:break
  out.append(row);used+=n
  if len(out)>=max_items:break
 return out
def repair_citation_placement(text):
 value=str(text or '');names=['Lo que indica la documentación','Orientación complementaria','Antes de continuar'];pos=[(re.search(re.escape(n),value,re.I).start() if re.search(re.escape(n),value,re.I) else -1) for n in names]
 if not (all(p>=0 for p in pos) and pos==sorted(pos)):return value,False
 rest=re.sub(r'\s*\[(R\d+)\]','',value[pos[1]:]);return value[:pos[1]]+rest,rest!=value[pos[1]:]
def validate_internal(text,finish_reason=None,valid_ids=None):
 value=str(text or '').strip();names=['Lo que indica la documentación','Orientación complementaria','Antes de continuar'];pos=[(re.search(re.escape(n),value,re.I).start() if re.search(re.escape(n),value,re.I) else -1) for n in names];ordered=all(p>=0 for p in pos) and pos==sorted(pos);complete=str(finish_reason or '').casefold() not in {'length','max_tokens'};first=value[pos[0]:pos[1]] if ordered else '';rest=value[pos[1]:] if ordered else value;doc=set(re.findall(r'\[(R\d+)\]',first));internal=set(re.findall(r'\[(R\d+)\]',rest));known=set(valid_ids or []);safe=bool(value) and ordered and not internal and doc.issubset(known)
 return safe and complete,{'safe_partial':safe,'sections_present':[n for n,p in zip(names,pos) if p>=0],'separation_valid':ordered,'finish_complete':complete,'documented_citations':sorted(doc),'internal_citations':sorted(internal),'unknown_citations':sorted((doc|internal)-known)}
def fingerprint(message,u,r,a,model=''):
 payload={'q':' '.join(str(message).split()).casefold(),'goal':u.get('current_goal'),'assessment':a.get('status'),'evidence':[(_stable(e)) for e in authorized_evidence(r)],'model':model,'prompt':PROMPT_VERSION};return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
class ControlledInternalKnowledgeComposer:
 def __init__(self,gateway,max_tokens=420):self.gateway=gateway;self.max_tokens=max(320,min(520,int(max_tokens)));self.last_provider_result={};self.validation={};self.attempts=[]
 def compose(self,message,u,r,a):
  from app.llm_gateway.models import LLMRequest
  ev=authorized_evidence(r);payload=enrich_internal_payload({'question':message,'goal':u.get('current_goal'),'documentation_assessment':a,'authorized_evidence':ev},r.get('_answer_context') or {},u);res=self.gateway.complete(LLMRequest([{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],'agent_core_v2_clean_internal_knowledge',self.max_tokens,0.0,None));self.attempts=[res.to_dict()];ids=[x['id'] for x in ev];ok,diag=validate_internal(res.text if res.ok else '',res.finish_reason,ids)
  if res.ok and not ok and diag.get('separation_valid') and diag.get('finish_complete'):
   repaired,changed=repair_citation_placement(res.text)
   if changed:res.text=repaired;ok,diag=validate_internal(repaired,res.finish_reason,ids);diag['deterministic_citation_repair']=True
  self.validation={**diag,'retry_used':False,'attempt_count':1,'selected_attempt':1,'published_partial':False,'selected_evidence_ids':ids,'authorized_stable_ids':[x['stable_id'] for x in ev],'answer_context_used':bool(payload.get('previous_answer_context'))};self.last_provider_result={**res.to_dict(),'selected_attempt':1,'attempts':self.attempts,'aggregate_usage':res.usage,'aggregate_latency_ms':float(getattr(res,'latency_ms',0) or 0)}
  if not res.ok:return AgentResponse('La documentación no es suficiente y no fue posible generar orientación complementaria.','internal_knowledge_provider_degraded',False)
  if not ok:return AgentResponse('Encontré orientación relacionada, pero no puedo publicarla sin una separación documental válida.','internal_knowledge_separation_guard',False,res.provider,res.model,res.usage,res.finish_reason)
  return AgentResponse(f'{WARNING}\n\n{str(res.text).strip()}','controlled_internal_knowledge',True,res.provider,res.model,res.usage,res.finish_reason)
