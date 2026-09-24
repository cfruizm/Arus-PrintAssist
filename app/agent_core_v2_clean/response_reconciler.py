from .semantic_contract import build_response_contract,validate_response_contract

def reconcile(result,memory):
 u=type("U",(),result.get("understanding") or {})();contract=build_response_contract(memory,u,result.get("retrieval") or {});validation=validate_response_contract((result.get("answer") or {}).get("text"),contract)
 result["response_contract"]=contract;result["response_reconciliation"]=validation
 if (result.get("answer") or {}).get("mode")=="natural_support" and str((result.get("answer") or {}).get("finish_reason") or "").casefold() in {"length","max_tokens"}:
  result.setdefault("functional_events",[]).append({"type":"truncated_natural_response_suppressed","severity":"high"})
  result["answer"]={"text":"La orientación quedó incompleta y no la publicaré de forma parcial. Retomaré la comprobación con evidencia documentada en el siguiente turno.","mode":"natural_length_guard","knowledge_used":False,"documented_evidence_used":False,"internal_knowledge_used":False,"knowledge_mode":"none"}
 if (result.get("answer") or {}).get("mode")=="retrieval_diagnostic":
  u=result.get("understanding") or {};intent=str(u.get("intent") or "unknown");act=str(u.get("user_act") or "new_request")
  result.setdefault("functional_events",[]).append({"type":"diagnostic_text_suppressed","severity":"high","reason":"no_terminal_answer","intent":intent,"user_act":act})
  if intent=="social" or act=="social": text="Hola. ¿Qué necesitas revisar sobre el servicio de impresión?";mode="social_recovery"
  elif intent=="capabilities" or act=="request_capabilities": text="Puedo explicar productos y conceptos de impresión, consultar procedimientos y requisitos documentados, orientar diagnósticos y preparar información para escalamiento.";mode="capabilities_recovery"
  elif (result.get("retrieval") or {}).get("count"):
   text="Encontré información relacionada, pero no quedó autorizada para responder con seguridad. Necesito precisar el producto o contexto antes de darte un procedimiento.";mode="evidence_scope_clarification"
  else:
   text="No encontré evidencia documental suficiente para responder esta consulta con seguridad.";mode="no_evidence_recovery"
  result["answer"]={"text":text,"mode":mode,"knowledge_used":False,"documented_evidence_used":False,"internal_knowledge_used":False,"knowledge_mode":"none"}
 return result



