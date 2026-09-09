from __future__ import annotations
import hashlib,json,re,unicodedata
from .models import AgentResponse
PROMPT_VERSION="controlled_internal_knowledge_v6_no_pseudo_procedure"
WARNING="⚠️ **Complemento con conocimiento general del modelo, no respaldado por la documentación recuperada**"
SYSTEM="""Actúa como colega de soporte empresarial de impresión. Responde de forma completa, concreta y prudente. Usa exactamente: 1) Lo que sí indica la documentación, 2) Orientación general complementaria, 3) Límites y verificación necesaria. La primera sección solo puede usar extractos suministrados y citas [R#]. Si ningún extracto responde a la operación solicitada, dilo en una frase y no cites contenido meramente comercial. En la orientación general incluye únicamente mecanismos directamente relacionados con la tarea. Considera administración local, directorios corporativos, sincronización de atributos, autoservicio o autenticación en dispositivo solo cuando la consulta trate sobre identidad, acceso, usuarios, credenciales o autenticación. Para firmware, red, colas, monitoreo, instalación u otras operaciones, usa verificaciones propias de esa tarea. No rellenes la respuesta con mecanismos ajenos al objetivo. No afirmes rutas, claves, versiones, botones o políticas exactas sin evidencia. Si la documentación no contiene el procedimiento exacto, no conviertas nombres habituales de menús, certificados, servidores, credenciales o integraciones posibles en pasos recomendados. Expresa las posibilidades como hipótesis que deben confirmarse. En la tercera sección separa claramente datos faltantes, comprobaciones seguras y acciones que requieren documentación del fabricante. No repitas como instrucción exacta aquello que acabas de declarar no documentado. En las secciones 2 y 3 no uses citas. Termina con verificaciones concretas. Máximo 260 palabras."""
RETRY_SYSTEM="""Reescribe la respuesta anterior en máximo 190 palabras. Conserva exactamente las tres secciones exigidas y termina la tercera sección. Corrige estructura, orden y citas: las referencias [R#] solo pueden aparecer en la primera sección; elimina todas las citas de las secciones 2 y 3. No agregues hechos nuevos."""

def _norm(value):
 return ''.join(c for c in unicodedata.normalize('NFKD',str(value or '').casefold()) if not unicodedata.combining(c))
def _terms(value):
 return {x for x in re.findall(r'[a-z0-9]{3,}',_norm(value)) if x not in {'como','para','the','and','con','una','del','los','las','que','por','explicar','realizar'}}
def evidence_excerpt(retrieval,question='',goal='',max_items=4,max_chars=3600):
 query=_terms(f'{question} {goal}');ranked=[]
 for pos,e in enumerate(retrieval.get('evidence') or []):
  text=' '.join(str(e.get('text') or '').split());hay=_terms(f"{e.get('title','')} {text}");overlap=len(query & hay);density=overlap/max(1,len(query));ranked.append((density,overlap,-pos,e,text))
 ranked.sort(reverse=True,key=lambda x:(x[0],x[1],x[2]));out=[];used=0
 for density,overlap,_,e,text in ranked:
  if overlap<=0:continue
  row={'id':e.get('id'),'title':e.get('title'),'page':e.get('page'),'text':text[:1200],'query_overlap':overlap};n=len(json.dumps(row,ensure_ascii=False))
  if out and used+n>max_chars:break
  out.append(row);used+=n
  if len(out)>=max_items:break
 return out

def validate_internal(text,finish_reason=None,valid_ids=None):
 value=str(text or '').strip();names=['Lo que sí indica la documentación','Orientación general complementaria','Límites y verificación necesaria'];positions=[]
 for name in names:
  m=re.search(re.escape(name),value,re.I);positions.append(m.start() if m else -1)
 ordered=all(p>=0 for p in positions) and positions==sorted(positions);complete=str(finish_reason or '').casefold() not in {'length','max_tokens'};first=value[positions[0]:positions[1]] if ordered else '';rest=value[positions[1]:] if ordered else value;doc=set(re.findall(r'\[(R\d+)\]',first));internal=set(re.findall(r'\[(R\d+)\]',rest));known=set(valid_ids or []);valid=bool(value) and ordered and complete and not internal and doc.issubset(known)
 return valid,{'sections_present':[n for n,p in zip(names,positions) if p>=0],'separation_valid':ordered,'finish_complete':complete,'documented_citations':sorted(doc),'internal_citations':sorted(internal),'unknown_citations':sorted((doc|internal)-known)}
def fingerprint(message,u,r,a,model=''):
 payload={'q':' '.join(str(message).split()).casefold(),'goal':u.get('current_goal'),'assessment':a.get('status'),'evidence':[(e.get('id'),e.get('url') or e.get('source')) for e in r.get('evidence') or []],'model':model,'prompt':PROMPT_VERSION};return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
class ControlledInternalKnowledgeComposer:
 def __init__(self,gateway,max_tokens=420):self.gateway=gateway;self.max_tokens=max(320,min(520,int(max_tokens)));self.last_provider_result={};self.validation={};self.attempts=[]
 def _call(self,messages,max_tokens):
  from app.llm_gateway.models import LLMRequest
  res=self.gateway.complete(LLMRequest(messages,'agent_core_v2_clean_internal_knowledge',max_tokens,0.0,None));self.attempts.append(res.to_dict());return res
 def compose(self,message,u,r,a):
  ev=evidence_excerpt(r,message,u.get('current_goal') or '');payload={'question':message,'goal':u.get('current_goal'),'documentation_assessment':a,'documented_excerpt':ev};messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}];res=self._call(messages,self.max_tokens);valid_ids=[str(x.get('id')) for x in ev];ok,self.validation=validate_internal(res.text if res.ok else '',res.finish_reason,valid_ids)
  if res.ok and not ok:
   retry=[{'role':'system','content':SYSTEM+'\n'+RETRY_SYSTEM},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))},{'role':'assistant','content':str(res.text or '')},{'role':'user','content':'Entrega ahora la versión completa y compacta.'}];res=self._call(retry,320);ok,self.validation=validate_internal(res.text if res.ok else '',res.finish_reason,valid_ids);self.validation['retry_used']=True
  else:self.validation['retry_used']=False
  self.validation['attempt_count']=len(self.attempts);self.validation['selected_evidence_ids']=valid_ids
  # Preserve the gateway result contract so telemetry keeps purpose and latency.
  selected=res.to_dict()
  selected['selected_attempt']=len(self.attempts)
  selected['attempts']=self.attempts
  selected['aggregate_usage']={
   'prompt_tokens':sum(int((x.get('usage') or {}).get('prompt_tokens',0)) for x in self.attempts),
   'completion_tokens':sum(int((x.get('usage') or {}).get('completion_tokens',0)) for x in self.attempts),
   'total_tokens':sum(int((x.get('usage') or {}).get('total_tokens',0)) for x in self.attempts),
  }
  selected['aggregate_latency_ms']=sum(float(x.get('latency_ms') or 0.0) for x in self.attempts)
  self.last_provider_result=selected
  if not res.ok:return AgentResponse('La documentación no es suficiente y no fue posible generar orientación complementaria.','internal_knowledge_provider_degraded',False)
  if not ok:return AgentResponse('La orientación complementaria no pudo completarse de forma segura. No mostraré contenido parcial o ambiguo.','internal_knowledge_separation_guard',False,res.provider,res.model,res.usage,res.finish_reason)
  return AgentResponse(f'{WARNING}\n\n{str(res.text).strip()}','controlled_internal_knowledge',True,res.provider,res.model,res.usage,res.finish_reason)
