import json
from .models import AgentResponse
from .memory import compact_context
SYSTEM="""Natural enterprise printing-support colleague. Use the user's language. Help first. Ask one targeted question only when required. Retrieval is disabled in this foundation: never invent exact menus, commands, values or product procedures. Do not claim undocumented meanings for error codes. Concise."""
class NaturalResponseComposer:
 def __init__(self,gateway,max_tokens=220):self.gateway=gateway;self.max_tokens=max(120,min(300,int(max_tokens)));self.last_provider_result={}
 def compose(self,message,m,u,d):
  if d.action=="redirect_scope":return AgentResponse("Ese tema está fuera de mi alcance de soporte de impresión. Si quieres, continuamos con el caso técnico.","out_of_scope")
  if d.action=="cancel":m.pending_goal.status="inactive";return AgentResponse("Listo, cancelé el flujo actual. ¿Qué necesitas revisar ahora?","cancelled")
  if d.action=="degraded_continue":return AgentResponse("No pude interpretar este turno de forma confiable. Conservé el estado anterior sin aplicar cambios.","provider_degraded")
  if d.action=="defer_to_retrieval":
   if u.intent=="conceptual":text="Entendí la consulta conceptual. La conservaré para responderla con documentación en la siguiente fase, sin inventar características."
   elif u.intent=="procedural":text="Entendí el procedimiento solicitado. Lo conservaré para consultar la documentación en la siguiente fase, sin inventar pasos."
   else:text="Entendí la solicitud y la conservaré para contrastarla con documentación en la siguiente fase."
   return AgentResponse(text,"retrieval_pending")
  from app.llm_gateway.models import LLMRequest
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps({"message":message,"memory":compact_context(m),"understanding":u.to_dict(),"decision":d.to_dict()},ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_response",self.max_tokens,0.,None));self.last_provider_result=r.to_dict()
  if not r.ok:return AgentResponse("Conservé el contexto, pero no pude generar la siguiente orientación.","provider_degraded")
  return AgentResponse(r.text.strip(),"natural_support",d.action in {"answer","diagnose"},r.provider,r.model,r.usage,r.finish_reason)
