from __future__ import annotations
import hashlib,json,re,unicodedata
from .models import AgentResponse
PROMPT_VERSION="procedural_documented_v9_refinement_scope_contract"
SYSTEM="""Eres un colega de soporte empresarial de impresión. Responde solo con la evidencia documental suministrada. Redacta una orientación operativa práctica, completa y proporcional al alcance de la pregunta en el idioma del usuario. Si el usuario pregunta por una decisión, opción, paso o dato específico dentro de un procedimiento ya tratado, responde directamente ese punto y no repitas el procedimiento completo. No afirmes que una validación fue ejecutada o verificada; formula las validaciones como acciones que el usuario debe realizar. Usa una o más secciones numeradas en Markdown con el formato **1. Título**. La evidencia puede describir pasos, requisitos, compatibilidad, comprobaciones, alternativas o límites. No inventes pasos ni completes vacíos con conocimiento interno. Conserva las relaciones lógicas de la evidencia: no conviertas alternativas en requisitos conjuntos, no sustituyas el método solicitado por otro parecido y no presentes una modalidad parcial como equivalente al objetivo. Si la evidencia describe opciones pero no el procedimiento exacto, indícalo. Cada párrafo o viñeta factual debe terminar con citas [R#]. Finaliza con **Validaciones finales** citada. No menciones el laboratorio."""
BOILERPLATE=("aviso legal","legal notice","información restringida","restricted information","control de registros","records control","control de cambios","change control","tiempo de retención","retention period","disposición final","final disposition")
OPERATIONAL_MARKERS=("validar","verificar","comprobar","confirmar","requisito","requiere","compatible","compatibilidad","admite","soporta","configurar","seleccionar","habilitar","instalar","conectar","sincronizar","importar","asignar","probar","actualizar","guardar","abrir","validate","verify","check","confirm","requirement","requires","required","compatible","compatibility","supports","supported","configure","configured","select","enable","enabled","install","connect","synchronize","sync","import","assign","test","update","authenticate","authentication","available","depends")
def _clean(text):return " ".join(str(text or "").split())
def _norm(text):return unicodedata.normalize("NFKD",str(text or "")).encode("ascii","ignore").decode().casefold()
def _usable(e):
 text=_clean(e.get("text"));low=_norm(text);signals=sum(1 for x in OPERATIONAL_MARKERS if x in low);noise=sum(1 for x in BOILERPLATE if x in low)
 return len(text)>=80 and signals>=1 and signals>noise
def evidence_pack(retrieval,max_items=8,max_chars=9000):
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
 return [int(x) for x in re.findall(r"(?m)^\s*(?:#{1,6}\s*)?\*\*(\d+)\s*[.)]\s+[^*\n]+\*\*\s*$",str(text or ""))]
def validate(text,ids,finish_reason=None,minimum_sections=1):
 cited=set(re.findall(r"\[(R\d+)\]",str(text or "")));sections=_section_numbers(text);ordered=not sections or sections==list(range(sections[0],sections[0]+len(sections)));complete=str(finish_reason or "").casefold() in {"","none","stop","completed"};valid=bool(str(text or "").strip()) and bool(sections) and ordered and bool(cited) and cited.issubset(set(ids)) and complete
 return valid,sorted(cited),{"sections":sections,"ordered":ordered,"finish_complete":complete,"cited_ids":sorted(cited)}
def readable_sources(retrieval,cited):
 by={str(e.get("id")):e for e in retrieval.get("evidence") or []};return [f"[{rid}] {by[rid].get('title') or 'Fuente sin título'}, página {by[rid].get('page') or 'N/D'}" for rid in cited if rid in by]
def fingerprint(message,understanding,retrieval,model=""):
 exp=retrieval.get("procedural_expansion") or {};payload={"q":" ".join(str(message).split()).casefold(),"goal":understanding.get("current_goal"),"evidence":[(e.get("id"),e.get("url") or e.get("source"),e.get("page")) for e in retrieval.get("evidence") or []],"pages":exp.get("pages"),"model":model,"prompt":PROMPT_VERSION};return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
class ProceduralAnswerComposer:
 def __init__(self,gateway,max_tokens=900):self.gateway=gateway;self.max_tokens=max(620,min(1100,int(max_tokens)));self.last_provider_result={};self.validation={}
 def compose(self,message,understanding,retrieval):
  exp=retrieval.get("procedural_expansion") or {};evidence=evidence_pack(retrieval)
  if not (exp.get("ok") and exp.get("same_document_only") and exp.get("ordered") and evidence):return AgentResponse("La evidencia operacional todavía no es suficiente o consistente para redactar una orientación segura.","procedural_evidence_guard",False)
  from app.llm_gateway.models import LLMRequest
  payload={"question":message,"goal":understanding.get("current_goal"),"document":exp.get("seed_document"),"pages":exp.get("pages"),"evidence":evidence}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_procedural_answer",self.max_tokens,0.,None));self.last_provider_result=r.to_dict()
  if not r.ok:return AgentResponse("Encontré evidencia operacional, pero no pude redactar la respuesta en este turno.","procedural_provider_degraded",False)
  text=str(r.text or "").strip()
  fields=(retrieval.get("query") or {}).get("fields") or {}
  details=fields.get("details") or {}
  relation=str(fields.get("topic_relation") or understanding.get("topic_relation") or "")
  act=str(fields.get("user_act") or understanding.get("user_act") or "")
  message_text=str(fields.get("current_message") or message or "").casefold()
  broad_request=bool(re.search(r"\b(todos?|todas?|completo|completa|completos|completas|entero|entera|principio a fin|paso a paso|full|complete|all steps|entire)\b",message_text))
  focused_followup=relation in {"same_topic","same_topic_refinement"} and act in {"follow_up","request_elaboration","answer_to_question"} and not broad_request and (relation=="same_topic_refinement" or bool(details.get("detail")) or understanding.get("intent") in {"requirements","verification","compatibility"})
  ok,cited,self.validation=validate(text,[str(x["id"]) for x in evidence],r.finish_reason,1)
  self.validation["focused_followup"]=focused_followup
  self.validation["minimum_sections"]=1
  self.validation["broad_request"]=broad_request
  if not ok:return AgentResponse("La estructura o las citas no superaron la validación. No mostraré instrucciones sin respaldo.","procedural_citation_guard",False,r.provider,r.model,r.usage,r.finish_reason)
  sources=readable_sources(retrieval,cited)
  if sources:text+="\n\n**Fuentes documentales**\n"+"\n".join(f"- {x}" for x in sources)
  return AgentResponse(text,"procedural_documented_answer",True,r.provider,r.model,r.usage,r.finish_reason)
