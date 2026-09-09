import json
from .models import AgentResponse
from .memory import compact_context
SYSTEM="""Natural enterprise printing-support colleague. Help first and stay within printing scope. Use memory and the decision. Ask one targeted question only when required. Advance troubleshooting without repeating validated checks. This foundation has retrieval disabled: never provide exact product menus, commands, values or step-by-step product procedures; explain that documentation will be consulted in the retrieval phase and ask only if a missing detail is necessary. Do not claim undocumented meanings for error codes. Do not mention classifiers or architecture. Concise Spanish."""
class NaturalResponseComposer:
 def __init__(self,gateway,max_tokens=180):self.gateway=gateway;self.max_tokens=max(120,int(max_tokens));self.last_provider_result={}
 def compose(self,message,m,u,d):
  if d.action=="redirect_scope":return AgentResponse("Ese tema está fuera de mi alcance de soporte de impresión. Si quieres, continuamos con el caso técnico o revisamos otra plataforma, proceso o dispositivo de impresión.","out_of_scope")
  if d.action=="cancel":m.pending_goal.status="inactive";return AgentResponse("Listo, cancelé el flujo actual. ¿Qué necesitas revisar ahora?","cancelled")
  if d.action=="degraded_continue":return AgentResponse("Registré tu respuesta y conservé el contexto del caso. El proveedor alcanzó temporalmente su límite, así que no voy a inventar el siguiente diagnóstico. Espera unos segundos y continúa con el mismo caso.","provider_degraded")
  if d.action=="defer_to_retrieval":return AgentResponse("Entendí la solicitud. Para darte un procedimiento confiable necesito consultar la documentación, función que se conectará en la siguiente fase. Por ahora conservaré este objetivo sin inventar pasos.","retrieval_pending")
  from app.llm_gateway.models import LLMRequest
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps({"message":message,"memory":compact_context(m),"understanding":u.to_dict(),"decision":d.to_dict()},ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_response",self.max_tokens,0.,None));self.last_provider_result=r.to_dict()
  if not r.ok:return AgentResponse("Conservé el contexto, pero el proveedor no pudo generar la siguiente orientación. Espera unos segundos y continúa; no necesitas repetir el caso.","provider_degraded",False,getattr(r,"provider",None),getattr(r,"model",None),{},getattr(r,"finish_reason",None))
  return AgentResponse(r.text.strip(),"natural_support",d.action in {"answer","diagnose"},r.provider,r.model,r.usage,r.finish_reason)
