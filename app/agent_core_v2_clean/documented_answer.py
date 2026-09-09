from __future__ import annotations
import json,re
from .models import AgentResponse

SYSTEM="""Eres un colega de soporte empresarial de impresión. Responde únicamente con la evidencia documental suministrada. Usa el idioma del usuario. Sé útil, directo y natural. No inventes menús, pasos, requisitos ni funciones. Cada afirmación factual debe terminar con una cita [R#]. Si la evidencia solo permite una respuesta parcial, indícalo claramente. Para una consulta conceptual, explica qué es, para qué sirve y sus funciones documentadas. No menciones procesos internos del laboratorio."""

def _evidence_pack(retrieval,max_items=4,max_chars=5200):
 items=[];used=0
 for e in retrieval.get("evidence") or []:
  text=" ".join(str(e.get("text") or "").split())
  if len(text)<40:continue
  item={"id":e.get("id"),"title":e.get("title"),"page":e.get("page"),"source":e.get("url") or e.get("source"),"text":text[:1800]}
  size=len(json.dumps(item,ensure_ascii=False))
  if items and used+size>max_chars:break
  items.append(item);used+=size
  if len(items)>=max_items:break
 return items

def _validate_citations(text,ids):
 cited=set(re.findall(r"\[(R\d+)\]",text or ""));return bool(text.strip()) and bool(cited) and cited.issubset(set(ids))

class DocumentedAnswerComposer:
 def __init__(self,gateway,max_tokens=260):self.gateway=gateway;self.max_tokens=max(180,min(420,int(max_tokens)));self.last_provider_result={}
 def compose(self,message,understanding,retrieval):
  evidence=_evidence_pack(retrieval)
  if not evidence:return AgentResponse("La recuperación no contiene evidencia suficiente para responder de forma documentada.","documented_insufficient",False)
  from app.llm_gateway.models import LLMRequest
  payload={"question":message,"intent":understanding.get("intent"),"goal":understanding.get("current_goal"),"evidence":evidence}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_documented_answer",self.max_tokens,0.,None));self.last_provider_result=r.to_dict()
  if not r.ok:return AgentResponse("Encontré documentación, pero no pude redactar la respuesta en este turno. Las fuentes recuperadas se conservaron.","documented_provider_degraded",False)
  text=str(r.text or "").strip();ids=[str(x["id"]) for x in evidence]
  if not _validate_citations(text,ids):return AgentResponse("Encontré documentación, pero la respuesta generada no superó la validación de citas. No mostraré una respuesta sin respaldo.","documented_citation_guard",False,r.provider,r.model,r.usage,r.finish_reason)
  return AgentResponse(text,"documented_answer",True,r.provider,r.model,r.usage,r.finish_reason)
