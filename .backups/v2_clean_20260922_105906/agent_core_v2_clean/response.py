from __future__ import annotations
import json,re
from .models import AgentResponse
from .memory import compact_context,failed_actions
from .evidence import repeated_failed_action

SYSTEM="""
Eres Arus PrintAssist, un compañero técnico de soporte N1 de servicios de impresión.
Responde en español natural, directo y útil.
Reglas:
1. Responde primero a la necesidad actual.
2. Usa solo los hechos confirmados por el usuario y las fuentes entregadas.
3. Para procedimientos, troubleshooting, requisitos o configuración: no inventes pasos, menús, comandos, rutas, valores o causas.
4. Puedes explicar conocimiento general solo si está claramente separado como orientación general y no se presenta como procedimiento del producto.
5. Nunca repitas una acción que ya falló; si aparece entre las acciones fallidas, busca otra validación o explica que falta evidencia.
6. Haz como máximo una pregunta, y solo cuando cambie materialmente el siguiente paso.
7. Si citas documentación, usa [R1], [R2], etc. únicamente para fuentes entregadas.
8. No afirmes que la documentación no contiene información si existen fuentes candidatas; di qué dimensión falta para decidir.
""".strip()

class ResponseComposer:
    def __init__(self,gateway,max_tokens=280):self.gateway=gateway;self.max_tokens=max(180,min(360,int(max_tokens)));self.last_provider_result={}
    def _deterministic(self,decision,memory):
        action=decision.get("action")
        if action=="social":return AgentResponse("Hola. Soy Arus PrintAssist. Cuéntame qué necesitas revisar del servicio de impresión.","deterministic")
        if action=="redirect_scope":return AgentResponse("Puedo ayudarte con consultas relacionadas con el servicio de impresión. Indícame el equipo, producto o proceso que quieres revisar.","out_of_scope")
        if action=="cancel":memory.pending_goal.status="inactive";return AgentResponse("Listo, cancelé el flujo actual. ¿Qué necesitas revisar ahora?","cancelled")
        if action=="degraded_continue":return AgentResponse("No pude interpretar este turno con suficiente confianza. Conservé el contexto anterior sin aplicar cambios.","provider_degraded")
        if action=="ask_one_question":
            target=str(decision.get("question_target") or "ese dato").strip()
            return AgentResponse(f"Para continuar necesito precisar {target}.","clarification")
        if action=="offer_escalation":return AgentResponse("De acuerdo. Puedo preparar el caso con el contexto y las validaciones ya realizadas para escalarlo.","escalation")
        return None
    def compose(self,message,memory,understanding,decision,retrieval=None):
        deterministic=self._deterministic(decision,memory)
        if deterministic:return deterministic
        sources=(retrieval or {}).get("evidence") or []
        selected=(retrieval or {}).get("selected") or sources[:4]
        failed=failed_actions(memory)
        from app.llm_gateway.models import LLMRequest
        payload={"message":message,"memory":compact_context(memory),"understanding":understanding.to_dict(),"decision":decision,"sources":[{"id":x.get("id"),"title":x.get("title"),"url":x.get("url"),"text":str(x.get("text") or "")[:3500]} for x in selected],"failed_actions":failed}
        system=SYSTEM
        if not sources:
            system += "\nNo hay evidencia recuperada. Para troubleshooting/procedimientos no des pasos específicos. Puedes explicar la limitación y pedir un solo dato discriminante."
        else:
            system += "\nLa respuesta documental debe citar las fuentes usadas con sus IDs [R1], [R2], etc."
        r=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}],"agent_core_v2_clean_response",self.max_tokens,0.0,None))
        self.last_provider_result=r.to_dict()
        if not r.ok:return AgentResponse("Conservé el contexto, pero no pude generar la siguiente orientación. El estado del caso no se perdió.","provider_degraded")
        text=str(r.text or "").strip()
        bad=repeated_failed_action(text,failed)
        if bad:
            text=(f"La validación ya realizada ({bad}) no resolvió el caso. No voy a recomendar repetirla. "
                  "Necesito contrastar otra validación documentada antes de indicar el siguiente paso.")
            return AgentResponse(text,"guardrail_replaced")
        return AgentResponse(text,"grounded_answer",bool(selected),r.provider,r.model,r.usage,r.finish_reason)
