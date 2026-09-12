from __future__ import annotations
import hashlib,json,re
from .models import AgentResponse

PROMPT_VERSION="conceptual_documented_v3_partial_length_visible"
SYSTEM="""Eres un colega de soporte empresarial de impresión. Responde únicamente con la evidencia documental suministrada. Usa el idioma del usuario. Sé útil, directo y natural. No inventes menús, pasos, requisitos ni funciones. Cada afirmación factual debe terminar con una cita [R#]. Si la evidencia solo permite una respuesta parcial, indícalo claramente. Para una consulta conceptual, explica qué es, para qué sirve y sus funciones documentadas. Para requisitos, enumera únicamente condiciones y compatibilidades respaldadas, sin exigir pasos operativos. En comparaciones, no recomiendes una alternativa sin cobertura equivalente de todas las opciones. No menciones procesos internos del laboratorio."""

def evidence_pack(retrieval,max_items=4,max_chars=5200):
 """Keeps the approved quality envelope. Only removes empty or exact-duplicate chunks."""
 items=[];used=0;seen=set()
 for e in retrieval.get("evidence") or []:
  text=" ".join(str(e.get("text") or "").split())
  if len(text)<40:continue
  signature=hashlib.sha256(text.casefold().encode()).hexdigest()
  if signature in seen:continue
  seen.add(signature)
  item={"id":e.get("id"),"title":e.get("title"),"page":e.get("page"),"source":e.get("url") or e.get("source"),"text":text[:1800]}
  size=len(json.dumps(item,ensure_ascii=False))
  if items and used+size>max_chars:break
  items.append(item);used+=size
  if len(items)>=max_items:break
 return items

def validate_citations(text,ids):
 cited=set(re.findall(r"\[(R\d+)\]",text or ""));return bool(str(text or "").strip()) and bool(cited) and cited.issubset(set(ids)),sorted(cited)
def answer_fingerprint(message,understanding,retrieval,model=""):
 payload={"q":" ".join(str(message).split()).casefold(),"goal":understanding.get("current_goal"),"intent":understanding.get("intent"),"retrieval":(retrieval.get("query") or {}).get("fingerprint"),"evidence":[(e.get("id"),e.get("url") or e.get("source"),e.get("page")) for e in retrieval.get("evidence") or []],"model":model,"prompt":PROMPT_VERSION}
 return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
def readable_sources(retrieval,cited_ids):
 by_id={str(e.get("id")):e for e in retrieval.get("evidence") or []};lines=[]
 for rid in cited_ids:
  e=by_id.get(rid)
  if not e:continue
  page=str(e.get("page") or "N/D");lines.append(f"[{rid}] {e.get('title') or 'Fuente sin título'}, página {page}")
 return lines
class DocumentedAnswerComposer:
 def __init__(self,gateway,max_tokens=260):self.gateway=gateway;self.max_tokens=max(220,min(420,int(max_tokens)));self.last_provider_result={};self.validation={}
 def compose(self,message,understanding,retrieval):
  evidence=evidence_pack(retrieval)
  if not evidence:return AgentResponse("La recuperación no contiene evidencia suficiente para responder de forma documentada.","documented_insufficient",False)
  from app.llm_gateway.models import LLMRequest
  payload={"question":message,"intent":understanding.get("intent"),"goal":understanding.get("current_goal"),"evidence":evidence}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_documented_answer",self.max_tokens,0.,None));self.last_provider_result=r.to_dict()
  if not r.ok:return AgentResponse("Encontré documentación, pero no pude redactar la respuesta en este turno. Las fuentes recuperadas se conservaron.","documented_provider_degraded",False)
  text=str(r.text or "").strip();valid,cited=validate_citations(text,[str(x["id"]) for x in evidence]);truncated=str(r.finish_reason or "").casefold() in {"length","max_tokens"}
  self.validation={"citations_valid":valid,"cited_ids":cited,"finish_reason":r.finish_reason,"truncated":truncated,"published_partial":bool(valid and truncated)}
  if not valid:return AgentResponse("Encontré documentación, pero la respuesta generada no superó la validación de citas. No mostraré una respuesta sin respaldo.","documented_citation_guard",False,r.provider,r.model,r.usage,r.finish_reason)
  if truncated:text += "\n\n> Respuesta parcial: el proveedor alcanzó el límite de salida. El contenido documentado disponible se conserva; puedes pedirme continuar."
  sources=readable_sources(retrieval,cited)
  if sources:text += "\n\n**Fuentes documentales**\n"+"\n".join(f"- {line}" for line in sources)
  mode="documented_answer_partial" if truncated else "documented_answer"
  return AgentResponse(text,mode,True,r.provider,r.model,r.usage,r.finish_reason)




