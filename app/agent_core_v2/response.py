import json,re
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=400):self.gateway=gateway;self.max_tokens=max_tokens
 def compose(self,message,decision,state,evidence):
  citable=evidence.get("citable") or []
  if decision.action=="ask_clarification":return {"mode":"clarification","text":decision.clarification_question or "Necesito una precisión adicional para continuar.","citations":[]}
  if decision.action!="retrieve":return {"mode":"directive","text":"","citations":[]}
  if not citable:return {"mode":"insufficient","text":self._limit(decision.intent,state),"citations":[]}
  if self.gateway is None:return {"mode":"documented","text":"Respuesta documentada pendiente del compositor LLM.","citations":[x["id"] for x in citable]}
  from app.llm_gateway.models import LLMRequest
  docs=[{"id":x["id"],"title":x["title"],"url":x["url"],"text":x["text"][:2400]} for x in citable[:3]]
  prompt={"message":message,"intent":decision.intent,"case":state.technical_case.__dict__,"sources":docs,"rules":["Usa solo las fuentes","Cita cada afirmación con [S#]","No inventes pasos","No repitas acciones fallidas","Máximo 220 palabras"]}
  r=self.gateway.complete(LLMRequest([{"role":"system","content":"Compón una respuesta de soporte en español, fiel a las fuentes."},{"role":"user","content":json.dumps(prompt,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self.max_tokens,0.,None))
  if not r.ok:return {"mode":"provider_error","text":self._limit(decision.intent,state),"citations":[]}
  used=set(re.findall(r"\[(S\d+)\]",r.text));valid={x["id"] for x in docs}
  if not used or used-valid:return {"mode":"invalid_citations","text":self._limit(decision.intent,state),"citations":[]}
  return {"mode":"documented","text":r.text.strip(),"citations":sorted(used),"provider":r.provider,"model":r.model,"usage":r.usage}
 def _limit(self,intent,state):
  if intent=="procedural":return "No encontré pasos directamente aplicables para este procedimiento. No usaré documentos tangenciales como instrucciones."
  if intent=="conceptual":return "No encontré una fuente específica suficiente para definir el producto con precisión."
  if intent=="requirements":return "No encontré requisitos específicos suficientes para confirmar compatibilidad o dependencias."
  return "La documentación disponible no permite indicar un siguiente paso confiable. Conserva la evidencia y evita repetir acciones que ya fallaron."
