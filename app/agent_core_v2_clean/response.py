import json
from .models import AgentResponse
from .memory import compact_context
SYSTEM="""Natural enterprise printing-support colleague. Use the user's language. Help first. Answer immediately when sufficiently clear. Resolve references to the last assistant question or last recommended check before introducing a different verification. Treat diagnostic hypotheses as possibilities, not confirmed causes. Ask exactly one short targeted question only when one missing fact is indispensable and materially changes the answer. If asking, do not include examples, technology lists, checklists, speculative mechanisms or a second question. Add at most one short sentence explaining why the answer matters. Retrieval is disabled here: never invent exact menus, commands, values or product procedures. Concise."""
class NaturalResponseComposer:
 def __init__(self,gateway,max_tokens=220):self.gateway=gateway;self.max_tokens=max(120,min(300,int(max_tokens)));self.last_provider_result={}
 def compose(self,message,m,u,d):
  if d.action=="redirect_scope":return AgentResponse("Ese tema está fuera de mi alcance de soporte de impresión. Si quieres, continuamos con el caso técnico.","out_of_scope")
  if d.action=="cancel":m.pending_goal.status="inactive";return AgentResponse("Listo, cancelé el flujo actual. ¿Qué necesitas revisar ahora?","cancelled")
  if d.action=="degraded_continue":return AgentResponse("No pude interpretar este turno de forma confiable. Conservé el estado anterior sin aplicar cambios.","provider_degraded")
  if d.action=="defer_to_retrieval":return AgentResponse("La solicitud quedó lista para contrastarla con la documentación.","retrieval_pending")
  if d.action=="ask_one_question" and not d.question_target:return AgentResponse("Puedo orientarte con lo disponible.","natural_support",True)
  from app.llm_gateway.models import LLMRequest
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps({"message":message,"memory":compact_context(m),"understanding":u.to_dict(),"decision":d.to_dict()},ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_response",min(self.max_tokens,150),0.,None));self.last_provider_result=r.to_dict()
  if not r.ok:return AgentResponse("Conservé el contexto, pero no pude generar la siguiente orientación.","provider_degraded")
  return AgentResponse(r.text.strip(),"natural_support",d.action in {"answer","diagnose"},r.provider,r.model,r.usage,r.finish_reason)




