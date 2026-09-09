from __future__ import annotations
import hashlib,json,re
from .models import AgentResponse
PROMPT_VERSION="controlled_internal_knowledge_v2_complete"
WARNING="⚠️ **Complemento con conocimiento general del modelo, no respaldado por la documentación recuperada**"
SYSTEM="""Actúa como colega de soporte empresarial de impresión. La documentación fue evaluada como parcial o insuficiente. Responde de forma breve y completa. Usa exactamente tres secciones: Lo que sí indica la documentación; Orientación general complementaria; Límites y verificación necesaria. En la primera sección limita las afirmaciones a los extractos suministrados y usa citas [R#]. En las otras dos secciones no uses citas. No inventes rutas exactas, botones, comandos, credenciales, valores, políticas ni versiones. Si no hay evidencia ejecutable, ofrece comprobaciones prudentes, no un procedimiento afirmativo. Finaliza siempre la última sección con una acción de verificación concreta."""
def evidence_excerpt(r,max_items=4,max_chars=4200):
 out=[];used=0
 for e in r.get("evidence") or []:
  text=" ".join(str(e.get("text") or "").split())[:1300]
  if not text:continue
  row={"id":e.get("id"),"title":e.get("title"),"page":e.get("page"),"text":text};n=len(json.dumps(row,ensure_ascii=False))
  if out and used+n>max_chars:break
  out.append(row);used+=n
  if len(out)>=max_items:break
 return out
def _sections(text):
 marks=[]
 for name in ("Lo que sí indica la documentación","Orientación general complementaria","Límites y verificación necesaria"):
  m=re.search(re.escape(name),text,re.I);marks.append((name,m.start() if m else -1))
 return marks
def validate_internal(text,finish_reason=None,valid_ids=None):
 value=str(text or "").strip();marks=_sections(value);positions=[p for _,p in marks];ordered=all(p>=0 for p in positions) and positions==sorted(positions);complete=str(finish_reason or "").casefold() not in {"length","max_tokens"};all_cites=set(re.findall(r"\[(R\d+)\]",value));first="";rest=value
 if ordered:first=value[positions[0]:positions[1]];rest=value[positions[1]:]
 doc_cites=set(re.findall(r"\[(R\d+)\]",first));internal_cites=set(re.findall(r"\[(R\d+)\]",rest));valid_set=set(valid_ids or []);valid=bool(value) and ordered and complete and not internal_cites and doc_cites.issubset(valid_set)
 return valid,{"sections_present":[n for n,p in marks if p>=0],"separation_valid":ordered,"finish_complete":complete,"documented_citations":sorted(doc_cites),"internal_citations":sorted(internal_cites),"unknown_citations":sorted(all_cites-valid_set)}
def fingerprint(message,u,r,a,model=""):
 payload={"q":" ".join(str(message).split()).casefold(),"goal":u.get("current_goal"),"assessment":a.get("status"),"evidence":[(e.get("id"),e.get("url") or e.get("source"),e.get("page")) for e in r.get("evidence") or []],"model":model,"prompt":PROMPT_VERSION};return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
class ControlledInternalKnowledgeComposer:
 def __init__(self,gateway,max_tokens=520):self.gateway=gateway;self.max_tokens=max(420,min(650,int(max_tokens)));self.last_provider_result={};self.validation={}
 def compose(self,message,u,r,a):
  from app.llm_gateway.models import LLMRequest
  ev=evidence_excerpt(r);req=LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps({"question":message,"goal":u.get("current_goal"),"documentation_assessment":a,"documented_excerpt":ev},ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_internal_knowledge",self.max_tokens,0.,None);res=self.gateway.complete(req);self.last_provider_result=res.to_dict()
  if not res.ok:return AgentResponse("La documentación no es suficiente y no fue posible generar orientación complementaria.","internal_knowledge_provider_degraded",False)
  body=str(res.text or "").strip();ok,self.validation=validate_internal(body,res.finish_reason,[str(x.get("id")) for x in ev])
  if not ok:
   msg="La orientación quedó incompleta por límite de longitud." if not self.validation.get("finish_complete") else "La orientación no separó correctamente documentación y conocimiento general."
   return AgentResponse(msg+" No mostraré contenido parcial o ambiguo.","internal_knowledge_separation_guard",False,res.provider,res.model,res.usage,res.finish_reason)
  return AgentResponse(f"{WARNING}\n\n{body}","controlled_internal_knowledge",True,res.provider,res.model,res.usage,res.finish_reason)
