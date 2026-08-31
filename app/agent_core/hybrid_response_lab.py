from __future__ import annotations
import json,re,time
from app.agent_core.response_evidence_policy import evaluate_document_support,build_response_contract
from app.llm_gateway.models import LLMRequest

SENSITIVE_PATTERNS=(r"\bfirmware\b",r"\bregistro\s+de\s+windows\b",r"\bbase\s+de\s+datos\b",r"\bfirewall\b",r"\bcertificad[oa]s?\b",r"\bcredenciales?\b",r"\blicencias?\b",r"\bgarant[ií]a\b",r"\brma\b",r"\bfacturaci[oó]n\b",r"\beliminar\s+cola\b",r"\bmodificar\s+servicios?\b",r"\bconfiguraci[oó]n\s+de\s+red\b")
FORBIDDEN_UNDOCUMENTED=("reinicia el servicio","reiniciar el servicio","desactiva","desactivar temporalmente","ping ","traceroute","firewall","registro de windows","base de datos","paper-cut-mf.log","papercut-mf.log","snmp poll")

def _tokens(text):return set(re.findall(r"[a-záéíóúñ0-9]{4,}",str(text or "").casefold()))
def _overlap(query,text):
 q=_tokens(query);t=_tokens(text);return 0.0 if not q else len(q&t)/len(q)
def is_sensitive_query(query):return any(re.search(p,str(query or "").casefold()) for p in SENSITIVE_PATTERNS)
def _canonical(item):return str(item.get("url") or item.get("source") or item.get("title") or "").strip().casefold()
def _hash(item):return str((item.get("metadata") or {}).get("content_hash") or "").strip()
def select_evidence(query,evidence,limit=3):
    query_tokens=_tokens(query);seen_hash=set();seen_id=set();ranked=[]
    for item in evidence or []:
        h=_hash(item);identity=_canonical(item)
        if (h and h in seen_hash) or identity in seen_id:continue
        if h:seen_hash.add(h)
        seen_id.add(identity)
        text=" ".join([str(item.get("title","")),str(item.get("url","")),str(item.get("text",""))])
        overlap=len(query_tokens&_tokens(text))/max(1,len(query_tokens))
        title_overlap=len(query_tokens&_tokens(item.get("title","")))/max(1,len(query_tokens))
        ranked.append((overlap+title_overlap*1.5,item))
    ranked.sort(key=lambda x:x[0],reverse=True)
    return [item for score,item in ranked[:limit] if score>0]
def assess_evidence(query,product,intent,evidence):
 selected=select_evidence(query,evidence,3)
 if not selected:return {"identity_score":0.0,"intent_alignment":0.0,"coverage_score":0.0,"source_quality":"none","contradictions":False,"sensitive":is_sensitive_query(query),"selected_evidence_count":0}
 combined=" ".join(str(x.get("title",""))+" "+str(x.get("source",""))+" "+str(x.get("text","")) for x in selected);identity=1.0 if product and product.casefold() in combined.casefold() else (0.5 if not product else 0.2);overlap=_overlap(query,combined);official=any("papercut.com" in str(x.get("url","")) or "hp.com" in str(x.get("url","")) or "epson" in str(x.get("url","")).casefold() for x in selected)
 return {"identity_score":round(identity,3),"intent_alignment":round(min(1.0,overlap*2.0),3),"coverage_score":round(min(1.0,overlap*1.6),3),"source_quality":"official" if official else "internal_or_unknown","contradictions":False,"sensitive":is_sensitive_query(query),"selected_evidence_count":len(selected)}
def deterministic_escalation_answer(query,case_state):
 product=", ".join(case_state.get("products") or []) or "producto no confirmado";symptom=", ".join(case_state.get("symptoms") or []) or query;failed=", ".join(case_state.get("failed_actions") or []) or "ninguna acción documentada"
 return f"""### Cobertura documental
La documentación recuperada corresponde a {product}, pero no permite indicar un procedimiento confiable para este escenario.

### Evidencia por recopilar
- Usuario y equipo afectados.
- Impresora o cola utilizada.
- Hora aproximada del evento.
- Estado visible y mensaje exacto, si existe.
- Acción ya realizada: {failed}.

### Escalamiento recomendado
Evita modificar servicios, red o configuración sin una fuente aplicable. Si el caso persiste, escala adjuntando la evidencia anterior y describiendo: {symptom}."""
def build_answer_messages(query,case_state,evidence,decision,contract):
 docs=[]
 for i,item in enumerate(evidence,1):docs.append({"id":f"S{i}","title":item.get("title"),"url":item.get("url"),"text":str(item.get("text",""))[:3000]})
 system="""Eres el modelo de respuesta técnica de Arus PrintAssist. Sigue exactamente el contrato de evidencia. Responde en español, máximo 220 palabras y máximo cuatro puntos. Termina la respuesta. En modo documented usa solo las fuentes entregadas y cita cada punto con [S1], [S2] o [S3]. Incluye al final 'Fuentes' con los IDs y títulos usados. No escribas 'documentación oficial' sin un ID. En modo hybrid separa contenido documentado y orientación general. No inventes procedimientos ni repitas acciones fallidas."""
 return [{"role":"system","content":system},{"role":"user","content":json.dumps({"query":query,"case_state":case_state,"evidence_decision":decision,"response_contract":contract,"sources":docs},ensure_ascii=False)}]
def validate_answer(answer,result,decision,valid_ids):
 violations=[];lower=str(answer or "").casefold()
 if result.get("finish_reason")=="length":violations.append("answer_truncated")
 if decision.get("response_mode")=="documented":
  used=set(re.findall(r"\[(S\d+)\]",str(answer or "")))
  if not used:violations.append("missing_source_ids")
  if used-set(valid_ids):violations.append("unknown_source_ids")
  if "documentación oficial" in lower or "documentacion oficial" in lower:violations.append("generic_official_source_claim")
 if decision.get("response_mode") in {"internal_general","escalate"}:
  for term in FORBIDDEN_UNDOCUMENTED:
   if term in lower:violations.append(f"forbidden_undocumented_instruction:{term.strip()}")
 if decision.get("disclosure_required") and "documentación" not in lower:violations.append("missing_documentation_disclosure")
 return {"compliant":not violations,"violations":violations}
def run_hybrid_response_lab(gateway,retrieval_result,query,case_state,intent,policy,max_tokens=400):
 all_evidence=retrieval_result.get("evidence") or [];evidence=select_evidence(query,all_evidence,3);product=((case_state.get("products") or [""])[0]);metrics=assess_evidence(query,product,intent,evidence);decision=evaluate_document_support(metrics,policy,intent);contract=build_response_contract(decision);started=time.perf_counter();selection={"input_count":len(all_evidence),"selected_count":len(evidence),"selected_sources":[{"id":f"S{i}","title":x.get("title"),"url":x.get("url")} for i,x in enumerate(evidence,1)]}
 if decision.response_mode=="escalate":answer=deterministic_escalation_answer(query,case_state);answer_result={"ok":True,"text":answer,"provider":"deterministic_policy","model":None,"purpose":"technical_answer_guardrail","latency_ms":0,"usage":{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0},"finish_reason":"stop","error_code":None,"error_message":None,"fallback_used":False,"fallback_provider":None,"metadata":{"llm_skipped":True,"reason":"policy_escalation"}}
 else:
  raw=gateway.complete(LLMRequest(build_answer_messages(query,case_state,evidence,decision.to_dict(),contract),"technical_answer",max(250,min(500,max_tokens)),0.0,None));answer_result=raw.to_dict();answer=answer_result.get("text","")
 compliance=validate_answer(answer,answer_result,decision.to_dict(),{f"S{i}" for i in range(1,len(evidence)+1)})
 if not compliance["compliant"]:answer=deterministic_escalation_answer(query,case_state);answer_result={**answer_result,"original_text":answer_result.get("text",""),"text":answer,"guardrail_replaced":True}
 return {"query":query,"intent":intent,"retrieval":retrieval_result,"evidence_selection":selection,"support_metrics":metrics,"evidence_decision":decision.to_dict(),"response_contract":contract,"answer_result":answer_result,"compliance":compliance,"total_latency_ms":round((time.perf_counter()-started)*1000,3),"production_response_changed":False}
