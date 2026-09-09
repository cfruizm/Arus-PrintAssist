from __future__ import annotations
import hashlib,json,re
from .models import AgentResponse

PROMPT_VERSION="procedural_documented_v4_semantic_fidelity"
SYSTEM="""Eres un colega de soporte empresarial de impresión. Responde solo con la evidencia documental suministrada. Redacta un procedimiento práctico, completo y compacto en el idioma del usuario. Usa secciones numeradas en Markdown con el formato **1. Título**. Dentro de cada sección agrupa acciones relacionadas para evitar una lista excesivamente larga. Conserva literalmente nombres de archivos, hojas, campos, botones, validaciones y advertencias. No inventes pasos ni completes vacíos con conocimiento interno. Conserva exactamente las relaciones lógicas de la evidencia: no conviertas alternativas (A o B) en requisitos conjuntos (A y B), no sustituyas el método solicitado por otro parecido y no presentes una modalidad parcial como equivalente al objetivo. Antes de responder, contrasta cada instrucción con la pregunta y con el fragmento citado. Si la evidencia describe opciones pero no el procedimiento exacto solicitado, indícalo en vez de deducir pasos. Cada párrafo o viñeta factual debe terminar con una o más citas [R#]. Finaliza siempre con una sección **Validaciones finales** citada. No incluyas introducciones largas ni menciones el laboratorio."""

BOILERPLATE=("aviso legal","información restringida","control de registros","control de cambios","tiempo de retención","disposición final")
ACTION_MARKERS=("objetivo","contenido","debemos","luego","botón","archivo","validar","nota","hoja","columna","consumo","proceso","actualizar","copiar","guardar","abrir")

def _clean(text):return " ".join(str(text or "").split())
def _usable(e):
 text=_clean(e.get("text"));low=text.casefold();actions=sum(1 for x in ACTION_MARKERS if x in low);noise=sum(1 for x in BOILERPLATE if x in low)
 return len(text)>=80 and actions>=2 and actions>noise

def evidence_pack(retrieval,max_items=8,max_chars=9000):
 """Keeps actionable evidence, removes legal/control-only chunks, preserves source IDs."""
 items=[];used=0;seen=set()
 for e in retrieval.get("evidence") or []:
  if not _usable(e):continue
  text=_clean(e.get("text"))[:2100];sig=hashlib.sha256(text.casefold().encode()).hexdigest()
  if sig in seen:continue
  seen.add(sig);item={"id":e.get("id"),"title":e.get("title"),"page":e.get("page"),"source":e.get("url") or e.get("source"),"text":text};size=len(json.dumps(item,ensure_ascii=False))
  if items and used+size>max_chars:break
  items.append(item);used+=size
  if len(items)>=max_items:break
 return items

def _section_numbers(text):
 # Accepts 1. Title, **1. Title**, and ### 1. Title without hard-coding any domain phrase.
 return [int(x) for x in re.findall(r"(?m)^\s*(?:#{1,6}\s*)?(?:\*\*)?(\d+)\s*[.)]",str(text or ""))]
def validate(text,ids,finish_reason=None):
 cited=set(re.findall(r"\[(R\d+)\]",str(text or "")));sections=_section_numbers(text);ordered=sections==sorted(set(sections));complete=str(finish_reason or "").casefold() not in {"length","max_tokens"}
 valid=bool(str(text or "").strip()) and len(sections)>=2 and ordered and bool(cited) and cited.issubset(set(ids)) and complete
 return valid,sorted(cited),{"sections":sections,"ordered":ordered,"finish_complete":complete,"cited_ids":sorted(cited)}
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
 def __init__(self,gateway,max_tokens=900):self.gateway=gateway;self.max_tokens=max(620,min(1100,int(max_tokens)));self.last_provider_result={};self.validation={}
 def compose(self,message,understanding,retrieval):
  exp=retrieval.get("procedural_expansion") or {};evidence=evidence_pack(retrieval)
  if not (exp.get("ok") and exp.get("same_document_only") and exp.get("ordered") and evidence):return AgentResponse("La evidencia procedimental todavía no es suficiente o consistente para redactar instrucciones seguras.","procedural_evidence_guard",False)
  from app.llm_gateway.models import LLMRequest
  payload={"question":message,"goal":understanding.get("current_goal"),"document":exp.get("seed_document"),"pages":exp.get("pages"),"evidence":evidence}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_procedural_answer",self.max_tokens,0.,None));self.last_provider_result=r.to_dict()
  if not r.ok:return AgentResponse("Encontré el procedimiento, pero no pude redactarlo en este turno. La evidencia quedó conservada.","procedural_provider_degraded",False)
  text=str(r.text or "").strip();ok,cited,self.validation=validate(text,[str(x["id"]) for x in evidence],r.finish_reason)
  if not ok:
   reason="La generación quedó incompleta por límite de longitud." if not self.validation.get("finish_complete") else "La estructura o las citas no superaron la validación."
   return AgentResponse(f"{reason} No mostraré instrucciones parciales o sin respaldo.","procedural_citation_guard",False,r.provider,r.model,r.usage,r.finish_reason)
  sources=readable_sources(retrieval,cited)
  if sources:text+="\n\n**Fuentes documentales**\n"+"\n".join(f"- {x}" for x in sources)
  return AgentResponse(text,"procedural_documented_answer",True,r.provider,r.model,r.usage,r.finish_reason)
