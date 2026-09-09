from __future__ import annotations
import json
from .models import AgentResponse
from .memory import compact_context
SYSTEM="""You are a natural enterprise printing support colleague. Help first. Use the current message, reconstructed goal and case memory. If action is ask_one_question, acknowledge what is already understood and ask exactly one targeted question without repeating known details. If action is diagnose, advance the case with one useful diagnostic question or safe next check. If out of scope, redirect briefly without pretending not to understand. Do not invent exact product menus, commands or values. Do not mention internal architecture, classifiers or policies. Respond in the user's language, concise and conversational."""
class NaturalResponseComposer:
 def __init__(self,gateway,max_tokens=260):self.gateway=gateway;self.max_tokens=max(180,int(max_tokens))
 def compose(self,message,memory,u,d):
  if d.action=="redirect_scope":return AgentResponse("Ese tema está fuera de mi alcance de soporte de impresión. Si quieres, continuamos con el caso técnico o revisamos otra plataforma, proceso o dispositivo de impresión.","out_of_scope")
  if d.action=="cancel":memory.pending_goal.status="inactive";return AgentResponse("Listo, cancelé el flujo actual. ¿Qué necesitas revisar ahora?","cancelled")
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"memory":compact_context(memory),"understanding":u.to_dict(),"decision":d.to_dict()}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_response",self.max_tokens,0.,None))
  text=r.text.strip() if r.ok else ("Entendido. ¿Cuál es el dato más importante que falta para continuar?" if d.ask_one_question else "Entendido. Continuemos con el caso.")
  return AgentResponse(text,"natural_support" if r.ok else "safe_fallback",True if d.action in {"answer","diagnose"} else False,getattr(r,"provider",None),getattr(r,"model",None),getattr(r,"usage",{}),getattr(r,"finish_reason",None))
