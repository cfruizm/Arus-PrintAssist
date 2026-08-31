from __future__ import annotations
import json,re,time
from app.agent_core.response_evidence_policy import evaluate_document_support,build_response_contract
from app.llm_gateway.models import LLMRequest

SENSITIVE_TERMS=("firmware","registro de windows","base de datos","firewall","certificado","credencial","licencia","garantia","garantía","rma","facturacion","facturación","eliminar cola")
FORBIDDEN_UNDOCUMENTED=("reinicia el servicio","reiniciar el servicio","desactiva","desactivar temporalmente","ping ","traceroute","firewall","registro de windows","base de datos","paper-cut-mf.log","papercut-mf.log","snmp poll")

def _tokens(text):return set(re.findall(r"[a-záéíóúñ0-9]{4,}",str(text or "").casefold()))
def _overlap(query,text):
 q=_tokens(query);t=_tokens(text);return 0.0 if not q else len(q&t)/len(q)
def assess_evidence(query,product,intent,evidence):
 if not evidence:return {"identity_score":0.0,"intent_alignment":0.0,"coverage_score":0.0,"source_quality":"none","contradictions":False,"sensitive":any(x in query.casefold() for x in SENSITIVE_TERMS)}
 combined=" ".join(str(x.get("title",""))+" "+str(x.get("source",""))+" "+str(x.get("text","")) for x in evidence);identity=1.0 if product and product.casefold() in combined.casefold() else (0.5 if not product else 0.2);overlap=_overlap(query,combined);official=any("papercut.com" in str(x.get("url","")) or "hp.com" in str(x.get("url","")) or "epson" in str(x.get("url","")).casefold() for x in evidence)
 return {"identity_score":round(identity,3),"intent_alignment":round(min(1.0,overlap*2.0),3),"coverage_score":round(min(1.0,overlap*1.6),3),"source_quality":"official" if official else "internal_or_unknown","contradictions":False,"sensitive":any(x in query.casefold() for x in SENSITIVE_TERMS)}

def deterministic_escalation_answer(query,case_state,evidence):
 product=", ".join(case_state.get("products") or []) or "producto no confirmado";symptom=", ".join(case_state.get("symptoms") or []) or query;failed=", ".join(case_state.get("failed_actions") or []) or "ninguna acción documentada"
 return f"""### Cobertura documental
La documentación recuperada corresponde a {product}, pero no permite indicar un procedimiento confiable para este síntoma.

### Evidencia por recopilar
- Usuario y equipo afectados.
- Impresora o cola utilizada.
- Hora aproximada del envío.
- Estado visible del trabajo y mensaje exacto, si existe.
- Acción ya realizada: {failed}.

### Escalamiento recomendado
Evita modificar servicios, red o configuración sin una fuente aplicable. Si el síntoma persiste, escala el caso adjuntando la evidencia anterior y describiendo: {symptom}."""

def build_answer_messages(query,case_state,evidence,decision,contract):
 docs=[]
 for i,item in enumerate(evidence,1):docs.append({"id":f"S{i}","title":item.get("title"),"url":item.get("url"),"source":item.get("source"),"text":str(item.get("text",""))[:3500]})
 system="""Eres el modelo de respuesta técnica de Arus PrintAssist. Sigue exactamente el contrato de evidencia. No inventes citas ni procedimientos. Las afirmaciones documentadas solo pueden usar IDs entregados. En modo hybrid, separa la información documentada de la orientación general. No repitas acciones fallidas. No indiques cambios sensibles sin respaldo. Responde en no más de 350 palabras y termina la respuesta."""
 return [{"role":"system","content":system},{"role":"user","content":json.dumps({"query":query,"case_state":case_state,"evidence_decision":decision,"response_contract":contract,"sources":docs},ensure_ascii=False)}]

def validate_answer(answer,result,decision):
 violations=[];lower=str(answer or "").casefold()
 if result.get("finish_reason")=="length":violations.append("answer_truncated")
 if decision.get("response_mode") in {"internal_general","escalate"}:
  for term in FORBIDDEN_UNDOCUMENTED:
   if term in lower:violations.append(f"forbidden_undocumented_instruction:{term.strip()}")
 if decision.get("disclosure_required") and "documentación" not in lower:violations.append("missing_documentation_disclosure")
 return {"compliant":not violations,"violations":violations}

def run_hybrid_response_lab(gateway,retrieval_result,query,case_state,intent,policy,max_tokens=400):
 evidence=retrieval_result.get("evidence") or [];product=((case_state.get("products") or [""])[0]);metrics=assess_evidence(query,product,intent,evidence);decision=evaluate_document_support(metrics,policy,intent);contract=build_response_contract(decision);started=time.perf_counter()
 if decision.response_mode=="escalate":
  answer=deterministic_escalation_answer(query,case_state,evidence);answer_result={"ok":True,"text":answer,"provider":"deterministic_policy","model":None,"purpose":"technical_answer_guardrail","latency_ms":0,"usage":{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0},"finish_reason":"stop","error_code":None,"error_message":None,"fallback_used":False,"fallback_provider":None,"metadata":{"llm_skipped":True,"reason":"insufficient_troubleshooting_support"}}
 else:
  raw=gateway.complete(LLMRequest(build_answer_messages(query,case_state,evidence,decision.to_dict(),contract),"technical_answer",max(200,min(500,max_tokens)),0.0,None));answer_result=raw.to_dict();answer=answer_result.get("text","")
 compliance=validate_answer(answer,answer_result,decision.to_dict())
 if not compliance["compliant"]:
  answer=deterministic_escalation_answer(query,case_state,evidence);answer_result={**answer_result,"original_text":answer_result.get("text",""),"text":answer,"guardrail_replaced":True}
 return {"query":query,"retrieval":retrieval_result,"support_metrics":metrics,"evidence_decision":decision.to_dict(),"response_contract":contract,"answer_result":answer_result,"compliance":compliance,"total_latency_ms":round((time.perf_counter()-started)*1000,3),"production_response_changed":False}
