from __future__ import annotations
import hashlib,json,re
from .models import AgentResponse
PROMPT_VERSION="documented_v7_requirement_dimension_guard"
SYSTEM="""Eres un colega de soporte empresarial de impresión. Responde únicamente con la evidencia documental suministrada. Usa el idioma del usuario. Sé útil, directo y natural. No inventes menús, pasos, requisitos ni funciones. Cada afirmación factual debe terminar con una cita [R#]. Si la evidencia solo permite una respuesta parcial, indícalo claramente. Para una consulta conceptual, explica qué es, para qué sirve y sus funciones documentadas. Para requisitos, sintetiza de forma completa las categorías respaldadas por toda la evidencia disponible. Resume cada categoría en una o dos viñetas y evita enumerar autoridades, endpoints o valores secundarios salvo que el usuario los solicite. Prioriza cobertura completa y concisa sobre detalle exhaustivo. En comparaciones, no recomiendes una alternativa sin cobertura equivalente de todas las opciones. Antes de afirmar que una información solicitada no está documentada, revisa todos los fragmentos suministrados. Si la evidencia contiene la dimensión solicitada y valores asociados, enuméralos y no afirmes ausencia. No menciones procesos internos del laboratorio."""
def evidence_pack(retrieval,max_items=8,max_chars=6500):
 items=[];used=0;seen=set()
 for e in retrieval.get("evidence") or []:
  text=" ".join(str(e.get("text") or "").split())
  if len(text)<40:continue
  signature=hashlib.sha256(text.casefold().encode()).hexdigest()
  if signature in seen:continue
  seen.add(signature);item={"id":e.get("id"),"title":e.get("title"),"page":e.get("page"),"source":e.get("url") or e.get("source"),"text":text[:1800]};size=len(json.dumps(item,ensure_ascii=False))
  if items and used+size>max_chars:break
  items.append(item);used+=size
  if len(items)>=max_items:break
 return items

_STOP={"cuales","cuáles","especificamente","específicamente","requisitos","requisito","necesito","identify","specific","requirements","subject","para","sobre","tiene","tienen","cual","cuál","del","los","las","son","que","qué"}
def _norm(value):
 import unicodedata
 return " ".join("".join(c for c in unicodedata.normalize("NFKD",str(value or "").casefold()) if not unicodedata.combining(c)).split())
def requested_dimensions(message,understanding):
 subject=set(re.findall(r"[a-z0-9]+",_norm((understanding or {}).get("canonical_subject") or (understanding or {}).get("goal_updates",{}).get("subject"))))
 return sorted({x for x in re.findall(r"[a-z0-9]+",_norm(message)) if len(x)>=5 and x not in _STOP and x not in subject})
def dimension_coverage(message,understanding,evidence):
 terms=requested_dimensions(message,understanding);body=_norm(" ".join(str(x.get("text") or "") for x in evidence));covered=[x for x in terms if x in body]
 return {"requested":terms,"covered":covered,"missing":[x for x in terms if x not in body],"sufficient":not terms or bool(covered)}
def contradicted_absence(text,message,understanding,evidence):
 body=_norm(text);absence=any(x in body for x in ("no especifica","no contiene","no detalla","no proporciona","no documenta","no es posible responder","not specify","not contain","not document"))
 coverage=dimension_coverage(message,understanding,evidence)
 return bool(absence and coverage["covered"]),coverage

def validate_citations(text,ids):
 cited=set(re.findall(r"\[(R\d+)\]",text or ""));return bool(str(text or "").strip()) and bool(cited) and cited.issubset(set(ids)),sorted(cited)
def answer_fingerprint(message,understanding,retrieval,model=""):
 payload={"q":" ".join(str(message).split()).casefold(),"goal":understanding.get("current_goal"),"intent":understanding.get("intent"),"retrieval":(retrieval.get("query") or {}).get("fingerprint"),"evidence":[(e.get("id"),e.get("url") or e.get("source"),e.get("page")) for e in retrieval.get("evidence") or []],"model":model,"prompt":PROMPT_VERSION};return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
def readable_sources(retrieval,cited_ids):
 by_id={str(e.get("id")):e for e in retrieval.get("evidence") or []};return [f"[{rid}] {by_id[rid].get('title') or 'Fuente sin título'}, página {by_id[rid].get('page') or 'N/D'}" for rid in cited_ids if rid in by_id]
class DocumentedAnswerComposer:
 def __init__(self,gateway,max_tokens=260):self.gateway=gateway;self.max_tokens=max(260,min(720,int(max_tokens)));self.last_provider_result={};self.validation={}
 def compose(self,message,understanding,retrieval):
  req=understanding.get("intent")=="requirements";evidence=evidence_pack(retrieval,16 if req else 8,14000 if req else 6500)
  if not evidence:return AgentResponse("La recuperación no contiene evidencia suficiente para responder de forma documentada.","documented_insufficient",False)
  from app.llm_gateway.models import LLMRequest
  payload={"question":message,"intent":understanding.get("intent"),"goal":understanding.get("current_goal"),"evidence":evidence}
  limit=680 if understanding.get("intent")=="requirements" else self.max_tokens
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_documented_answer",limit,0.,None));self.last_provider_result=r.to_dict()
  if not r.ok:return AgentResponse("Encontré documentación, pero no pude redactar la respuesta en este turno. Las fuentes recuperadas se conservaron.","documented_provider_degraded",False)
  text=str(r.text or "").strip();contradiction,dimension_check=contradicted_absence(text,message,understanding,evidence);valid,cited=validate_citations(text,[str(x["id"]) for x in evidence]);truncated=str(r.finish_reason or "").casefold() in {"length","max_tokens"};pages={str(x.get("page") or "") for x in evidence if x.get("page")};coverage=understanding.get("intent")!="requirements" or len(pages)<2 or len(cited)>=2;valid=bool(valid and coverage and not contradiction)
  self.validation={"citations_valid":valid,"cited_ids":cited,"finish_reason":r.finish_reason,"truncated":truncated,"published_partial":bool(valid and truncated),"requirements_coverage_valid":coverage,"evidence_pages":sorted(pages),"requested_dimension_coverage":dimension_check,"contradicted_absence_blocked":contradiction}
  if contradiction:return AgentResponse("La respuesta generada contradecía la evidencia documental recuperada y fue bloqueada antes de publicarse. Intenta nuevamente para regenerar la síntesis documentada.","documented_evidence_contradiction_guard",False,r.provider,r.model,r.usage,r.finish_reason)
  if not valid:return AgentResponse("Encontré documentación, pero la respuesta generada no cubrió suficientemente la evidencia o no superó la validación de citas.","documented_citation_guard",False,r.provider,r.model,r.usage,r.finish_reason)
  if truncated:text+="\n\n> Respuesta parcial: el proveedor alcanzó el límite de salida. El contenido documentado disponible se conserva; puedes pedirme continuar."
  sources=readable_sources(retrieval,cited)
  if sources:text+="\n\n**Fuentes documentales**\n"+"\n".join(f"- {x}" for x in sources)
  return AgentResponse(text,"documented_answer_partial" if truncated else "documented_answer",True,r.provider,r.model,r.usage,r.finish_reason)
