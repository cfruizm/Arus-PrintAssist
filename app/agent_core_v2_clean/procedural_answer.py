from __future__ import annotations
import hashlib,json,re
from .models import AgentResponse

PROMPT_VERSION="procedural_documented_v1"
SYSTEM="""Eres un colega de soporte empresarial de impresión. Responde solo con la evidencia documental suministrada. Redacta un procedimiento práctico, ordenado y completo en el idioma del usuario. Conserva nombres de archivos, hojas, campos, botones, validaciones y advertencias exactamente como aparecen. No inventes pasos ni completes vacíos con conocimiento interno. Cada paso y condición factual debe terminar con una cita [R#]. Si la evidencia empieza o termina a mitad de un paso, advierte que el procedimiento recuperado es parcial. No menciones el laboratorio."""

def _usable(e):
 text=" ".join(str(e.get("text") or "").split())
 # Excludes pages with only legal/control boilerplate without encoding product terms.
 markers=("objetivo","contenido","•","","debemos","luego","para ","paso","botón","archivo","validar","nota")
 return len(text)>=80 and any(x in text.casefold() for x in markers)
def evidence_pack(retrieval,max_items=8,max_chars=10500):
 items=[];used=0;seen=set()
 for e in retrieval.get("evidence") or []:
  if not _usable(e):continue
  text=" ".join(str(e.get("text") or "").split())[:2200]
  sig=hashlib.sha256(text.casefold().encode()).hexdigest()
  if sig in seen:continue
  seen.add(sig);item={"id":e.get("id"),"title":e.get("title"),"page":e.get("page"),"source":e.get("url") or e.get("source"),"text":text};size=len(json.dumps(item,ensure_ascii=False))
  if items and used+size>max_chars:break
  items.append(item);used+=size
  if len(items)>=max_items:break
 return items
def validate(text,ids):
 cited=set(re.findall(r"\[(R\d+)\]",str(text or "")));numbered=len(re.findall(r"(?m)^\s*\d+[.)]",str(text or "")))
 return bool(str(text or "").strip()) and bool(cited) and cited.issubset(set(ids)) and numbered>=2,sorted(cited)
def readable_sources(retrieval,cited):
 by={str(e.get("id")):e for e in retrieval.get("evidence") or []};out=[]
 for rid in cited:
  e=by.get(rid)
  if e:out.append(f"[{rid}] {e.get('title') or 'Fuente sin título'}, página {e.get('page') or 'N/D'}")
 return out
def fingerprint(message,understanding,retrieval,model=""):
 exp=retrieval.get("procedural_expansion") or {};payload={"q":" ".join(str(message).split()).casefold(),"goal":understanding.get("current_goal"),"evidence":[(e.get("id"),e.get("url") or e.get("source"),e.get("page")) for e in retrieval.get("evidence") or []],"pages":exp.get("pages"),"model":model,"prompt":PROMPT_VERSION}
 return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
class ProceduralAnswerComposer:
 def __init__(self,gateway,max_tokens=620):self.gateway=gateway;self.max_tokens=max(420,min(800,int(max_tokens)));self.last_provider_result={}
 def compose(self,message,understanding,retrieval):
  exp=retrieval.get("procedural_expansion") or {};evidence=evidence_pack(retrieval)
  if not (exp.get("ok") and exp.get("same_document_only") and exp.get("ordered") and evidence):return AgentResponse("La evidencia procedimental todavía no es suficiente o consistente para redactar instrucciones seguras.","procedural_evidence_guard",False)
  from app.llm_gateway.models import LLMRequest
  payload={"question":message,"goal":understanding.get("current_goal"),"document":exp.get("seed_document"),"pages":exp.get("pages"),"evidence":evidence}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_procedural_answer",self.max_tokens,0.,None));self.last_provider_result=r.to_dict()
  if not r.ok:return AgentResponse("Encontré el procedimiento, pero no pude redactarlo en este turno. La evidencia quedó conservada.","procedural_provider_degraded",False)
  text=str(r.text or "").strip();ok,cited=validate(text,[str(x["id"]) for x in evidence])
  if not ok:return AgentResponse("La respuesta procedimental generada no superó la validación de estructura y citas. No mostraré instrucciones sin respaldo.","procedural_citation_guard",False,r.provider,r.model,r.usage,r.finish_reason)
  sources=readable_sources(retrieval,cited)
  if sources:text+="\n\n**Fuentes documentales**\n"+"\n".join(f"- {x}" for x in sources)
  return AgentResponse(text,"procedural_documented_answer",True,r.provider,r.model,r.usage,r.finish_reason)
