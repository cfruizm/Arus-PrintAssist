from __future__ import annotations
import hashlib,json,re,unicodedata
from .models import AgentResponse
from .answer_context_policy import enrich_internal_payload
PROMPT_VERSION="controlled_internal_knowledge_v10_confirmed_context_scope"
WARNING="⚠️ **Orientación complementaria basada en conocimiento general del modelo**"
SYSTEM="""Actúa como colega de soporte empresarial de impresión. Responde concreta y prudentemente. Usa exactamente estos encabezados Markdown: ### Lo que indica la documentación, ### Orientación complementaria, ### Antes de continuar. La primera sección solo puede usar los extractos suministrados y citas [R#]. Si ningún extracto responde, dilo en una frase. La orientación debe responder al objetivo actual y, cuando exista contexto de una respuesta anterior, debe validar, precisar o corregir esa respuesta en vez de comenzar una lista genérica. Si la respuesta anterior asumió una modalidad no confirmada, indícalo claramente. No presentes una modalidad particular como si fuera todo el objetivo general. No contradigas detalles ya confirmados por el usuario. No vuelvas a pedir producto o plataforma si ya están en el objetivo, detalles o contexto previo. Distingue producto de sistema operativo. No introduzcas controladores, licencias, biometría, credenciales de servicio u otros componentes no presentes en la pregunta, la evidencia o el contexto previo. No afirmes rutas, claves, versiones, botones o políticas exactas sin evidencia. En las secciones 2 y 3 no uses citas. Evita listas universales de firmware, certificados, red, directorio o permisos si no se relacionan directamente con lo documentado o con el seguimiento. Termina con comprobaciones concretas y reversibles. Máximo 240 palabras."""
RETRY_SYSTEM="""Reescribe en máximo 170 palabras. Conserva los tres encabezados. Las citas [R#] solo pueden aparecer en la primera sección. Responde al seguimiento usando la respuesta anterior. Elimina listas genéricas y no agregues hechos nuevos."""

def _norm(value):return ''.join(c for c in unicodedata.normalize('NFKD',str(value or '').casefold()) if not unicodedata.combining(c))
def _terms(value):return {x for x in re.findall(r'[a-z0-9]{3,}',_norm(value)) if x not in {'como','para','the','and','con','una','del','los','las','que','por','explicar','realizar'}}
def evidence_excerpt(retrieval,question='',goal='',max_items=5,max_chars=4600):
 source=retrieval.get('generation_evidence') or retrieval.get('evidence') or [];query=_terms(f'{question} {goal}');ranked=[]
 for pos,e in enumerate(source):
  text=' '.join(str(e.get('text') or '').split());hay=_terms(f"{e.get('title','')} {text}");overlap=len(query&hay);ranked.append((overlap/max(1,len(query)),overlap,-pos,e,text))
 ranked.sort(reverse=True,key=lambda x:(x[0],x[1],x[2]));out=[];used=0
 for density,overlap,_,e,text in ranked:
  if overlap<=0 and out:continue
  row={'id':e.get('id'),'title':e.get('title'),'page':e.get('page'),'text':text[:1300],'carried_from_previous_answer':bool(e.get('carried_from_previous_answer'))};n=len(json.dumps(row,ensure_ascii=False))
  if out and used+n>max_chars:break
  out.append(row);used+=n
  if len(out)>=max_items:break
 return out

def repair_citation_placement(text):
 value=str(text or '')
 names=['Lo que indica la documentación','Orientación complementaria','Antes de continuar'];positions=[]
 for name in names:
  m=re.search(re.escape(name),value,re.I);positions.append(m.start() if m else -1)
 if not (all(p>=0 for p in positions) and positions==sorted(positions)):return value,False
 head=value[:positions[1]];rest=re.sub(r'\s*\[(R\d+)\]','',value[positions[1]:]);return head+rest,rest!=value[positions[1]:]

def validate_internal(text,finish_reason=None,valid_ids=None):
 value=str(text or '').strip();names=['Lo que indica la documentación','Orientación complementaria','Antes de continuar'];positions=[]
 for name in names:
  m=re.search(re.escape(name),value,re.I);positions.append(m.start() if m else -1)
 ordered=all(p>=0 for p in positions) and positions==sorted(positions);complete=str(finish_reason or '').casefold() not in {'length','max_tokens'};first=value[positions[0]:positions[1]] if ordered else '';rest=value[positions[1]:] if ordered else value;doc=set(re.findall(r'\[(R\d+)\]',first));internal=set(re.findall(r'\[(R\d+)\]',rest));known=set(valid_ids or []);safe=bool(value) and ordered and not internal and doc.issubset(known);valid=safe and complete
 return valid,{'safe_partial':safe,'sections_present':[n for n,p in zip(names,positions) if p>=0],'separation_valid':ordered,'finish_complete':complete,'documented_citations':sorted(doc),'internal_citations':sorted(internal),'unknown_citations':sorted((doc|internal)-known)}
def fingerprint(message,u,r,a,model=''):
 payload={'q':' '.join(str(message).split()).casefold(),'goal':u.get('current_goal'),'assessment':a.get('status'),'evidence':[(e.get('id'),e.get('url') or e.get('source')) for e in r.get('generation_evidence') or r.get('evidence') or []],'previous_goal':(r.get('_answer_context') or {}).get('goal'),'model':model,'prompt':PROMPT_VERSION};return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
class ControlledInternalKnowledgeComposer:
 def __init__(self,gateway,max_tokens=420):self.gateway=gateway;self.max_tokens=max(320,min(520,int(max_tokens)));self.last_provider_result={};self.validation={};self.attempts=[]
 def _call(self,messages,max_tokens):
  from app.llm_gateway.models import LLMRequest
  res=self.gateway.complete(LLMRequest(messages,'agent_core_v2_clean_internal_knowledge',max_tokens,0.0,None));row=res.to_dict();row['purpose']=row.get('purpose') or 'agent_core_v2_clean_internal_knowledge';row.setdefault('metadata',{})['attempted_purpose']='agent_core_v2_clean_internal_knowledge';self.attempts.append(row);return res
 def compose(self,message,u,r,a):
  ev=evidence_excerpt(r,message,u.get('current_goal') or '');payload={'question':message,'goal':u.get('current_goal'),'documentation_assessment':a,'documented_excerpt':ev};payload=enrich_internal_payload(payload,r.get('_answer_context') or {},u);messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}];first=self._call(messages,self.max_tokens);valid_ids=[str(x.get('id')) for x in ev];candidates=[];ok,diag=validate_internal(first.text if first.ok else '',first.finish_reason,valid_ids)
  if first.ok and not ok and diag.get('separation_valid') and not diag.get('unknown_citations') and diag.get('finish_complete'):
   repaired,changed=repair_citation_placement(first.text)
   if changed:first.text=repaired;ok,diag=validate_internal(repaired,first.finish_reason,valid_ids);diag['deterministic_citation_repair']=True
  candidates.append((first,ok,diag))
  if first.ok and not ok and not diag.get('safe_partial'):
   retry=[{'role':'system','content':SYSTEM+'\n'+RETRY_SYSTEM},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))},{'role':'assistant','content':str(first.text or '')},{'role':'user','content':'Entrega la versión completa y compacta.'}];second=self._call(retry,300);ok2,diag2=validate_internal(second.text if second.ok else '',second.finish_reason,valid_ids);candidates.append((second,ok2,diag2))
  def rank(item):
   res,valid,diagnostic=item;return (1 if valid else 0,1 if diagnostic.get('safe_partial') else 0,1 if diagnostic.get('finish_complete') else 0,len(str(res.text or '')))
  res,ok,self.validation=max(candidates,key=rank);selected_index=candidates.index((res,ok,self.validation))+1;partial=bool(not ok and self.validation.get('safe_partial'));self.validation.update({'retry_used':len(candidates)>1,'attempt_count':len(self.attempts),'selected_attempt':selected_index,'published_partial':partial,'selected_evidence_ids':valid_ids,'answer_context_used':bool(payload.get('previous_answer_context'))})
  selected=res.to_dict();selected['selected_attempt']=selected_index;selected['attempts']=self.attempts;selected['aggregate_usage']={'prompt_tokens':sum(int((x.get('usage') or {}).get('prompt_tokens',0)) for x in self.attempts),'completion_tokens':sum(int((x.get('usage') or {}).get('completion_tokens',0)) for x in self.attempts),'total_tokens':sum(int((x.get('usage') or {}).get('total_tokens',0)) for x in self.attempts)};selected['aggregate_latency_ms']=sum(float(x.get('latency_ms') or 0.0) for x in self.attempts);self.last_provider_result=selected
  if not res.ok:return AgentResponse('La documentación no es suficiente y no fue posible generar orientación complementaria.','internal_knowledge_provider_degraded',False)
  if not ok and not partial:return AgentResponse('La orientación complementaria no pudo completarse de forma segura.','internal_knowledge_separation_guard',False,res.provider,res.model,res.usage,res.finish_reason)
  text=f'{WARNING}\n\n{str(res.text).strip()}'
  if partial:text+='\n\n> Respuesta parcial: el proveedor alcanzó el límite de salida. Se conserva el contenido seguro disponible.'
  return AgentResponse(text,'controlled_internal_knowledge_partial' if partial else 'controlled_internal_knowledge',True,res.provider,res.model,res.usage,res.finish_reason)
