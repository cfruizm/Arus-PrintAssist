from __future__ import annotations
import hashlib, json, re
from .models import AgentResponse

PROMPT_VERSION = "controlled_internal_knowledge_v1"
WARNING = "⚠️ **Complemento con conocimiento general del modelo, no respaldado por la documentación recuperada**"
SYSTEM = """Actúa como colega de soporte empresarial de impresión. La documentación recuperada fue evaluada como parcial o insuficiente. Ofrece únicamente orientación general, prudente y reversible basada en conocimiento general del modelo. No inventes rutas exactas, nombres de botones, comandos, credenciales, valores, políticas, versiones, requisitos contractuales ni procedimientos específicos del entorno. No cites [R#] ni presentes conocimiento general como documentación. Separa claramente: Lo que sí indica la documentación, Orientación general complementaria, Límites y verificación necesaria. Si falta evidencia para ejecutar cambios, formula comprobaciones y próximos pasos, no instrucciones afirmativas. Mantén la respuesta breve y natural. No menciones el laboratorio."""

def evidence_excerpt(retrieval: dict, max_items: int = 3, max_chars: int = 3500) -> list[dict]:
    output=[]; used=0
    for item in retrieval.get("evidence") or []:
        text=" ".join(str(item.get("text") or "").split())[:1400]
        if not text: continue
        row={"id":item.get("id"),"title":item.get("title"),"page":item.get("page"),"text":text}
        size=len(json.dumps(row,ensure_ascii=False))
        if output and used+size>max_chars: break
        output.append(row); used+=size
        if len(output)>=max_items: break
    return output

def validate_internal(text: str) -> tuple[bool, dict]:
    value=str(text or "").strip(); citations=sorted(set(re.findall(r"\[R\d+\]", value)))
    required=["Lo que sí indica la documentación","Orientación general complementaria","Límites y verificación necesaria"]
    present=[heading for heading in required if heading.casefold() in value.casefold()]
    valid=bool(value) and not citations and len(present)==len(required)
    return valid,{"citations_found":citations,"required_sections":required,"sections_present":present,"separation_valid":len(present)==len(required)}

def fingerprint(message: str, understanding: dict, retrieval: dict, assessment: dict, model: str = "") -> str:
    payload={"q":" ".join(str(message).split()).casefold(),"goal":understanding.get("current_goal"),"assessment":assessment.get("status"),"reasons":assessment.get("reasons"),"evidence":[(e.get("id"),e.get("url") or e.get("source"),e.get("page")) for e in retrieval.get("evidence") or []],"model":model,"prompt":PROMPT_VERSION}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]

class ControlledInternalKnowledgeComposer:
    def __init__(self,gateway,max_tokens: int = 420):
        self.gateway=gateway; self.max_tokens=max(260,min(520,int(max_tokens))); self.last_provider_result={}; self.validation={}
    def compose(self,message: str,understanding: dict,retrieval: dict,assessment: dict) -> AgentResponse:
        from app.llm_gateway.models import LLMRequest
        payload={"question":message,"goal":understanding.get("current_goal"),"documentation_assessment":assessment,"documented_excerpt":evidence_excerpt(retrieval)}
        request=LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_internal_knowledge",self.max_tokens,0.0,None)
        result=self.gateway.complete(request); self.last_provider_result=result.to_dict()
        if not result.ok:
            return AgentResponse("La documentación no es suficiente y tampoco fue posible generar una orientación complementaria en este turno.","internal_knowledge_provider_degraded",False)
        body=str(result.text or "").strip(); ok,self.validation=validate_internal(body)
        if not ok:
            return AgentResponse("La orientación complementaria no superó la separación entre documentación y conocimiento general. No mostraré contenido ambiguo.","internal_knowledge_separation_guard",False,result.provider,result.model,result.usage,result.finish_reason)
        return AgentResponse(f"{WARNING}\n\n{body}","controlled_internal_knowledge",True,result.provider,result.model,result.usage,result.finish_reason)
