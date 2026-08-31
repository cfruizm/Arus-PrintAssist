from __future__ import annotations
import json,re,time
from app.agent_core.response_evidence_policy import evaluate_document_support,build_response_contract
from app.llm_gateway.models import LLMRequest

SENSITIVE_TERMS=("firmware","registro de windows","base de datos","firewall","certificado","credencial","licencia","garantia","garantía","rma","facturacion","facturación","eliminar cola")

def _tokens(text):return set(re.findall(r"[a-záéíóúñ0-9]{4,}",str(text or "").casefold()))
def _overlap(query,text):
 q=_tokens(query);t=_tokens(text)
 return 0.0 if not q else len(q&t)/len(q)
def assess_evidence(query,product,intent,evidence):
 if not evidence:return {"identity_score":0.0,"intent_alignment":0.0,"coverage_score":0.0,"source_quality":"none","contradictions":False,"sensitive":any(x in query.casefold() for x in SENSITIVE_TERMS)}
 combined=" ".join(str(x.get("title",""))+" "+str(x.get("source",""))+" "+str(x.get("text","")) for x in evidence)
 identity=1.0 if product and product.casefold() in combined.casefold() else (0.5 if not product else 0.2)
 overlap=_overlap(query,combined);official=any("papercut.com" in str(x.get("url","")) or "hp.com" in str(x.get("url","")) or "epson" in str(x.get("url","")).casefold() for x in evidence)
 return {"identity_score":round(identity,3),"intent_alignment":round(min(1.0,overlap*2.0),3),"coverage_score":round(min(1.0,overlap*1.6),3),"source_quality":"official" if official else "internal_or_unknown","contradictions":False,"sensitive":any(x in query.casefold() for x in SENSITIVE_TERMS)}

def build_answer_messages(query,case_state,evidence,policy_decision,contract):
 docs=[]
 for i,item in enumerate(evidence,1):docs.append({"id":f"S{i}","title":item.get("title"),"url":item.get("url"),"source":item.get("source"),"text":str(item.get("text",""))[:5000]})
 system="""Eres el modelo de respuesta técnica de Arus PrintAssist. Responde en español usando el contrato de evidencia indicado. No inventes citas. Las afirmaciones documentadas solo pueden citar IDs entregados. Si el modo es hybrid o internal_general, separa claramente la orientación general del modelo y muestra la advertencia antes de ella. La orientación interna solo puede incluir observaciones, recopilación de evidencia, explicaciones generales y acciones reversibles no invasivas. No indiques cambios sensibles sin documentación. No repitas acciones fallidas. Si el modo es escalate, explica qué evidencia recopilar y recomienda escalar. Devuelve texto claro, no JSON."""
 payload={"query":query,"case_state":case_state,"evidence_mode":policy_decision,"response_contract":contract,"sources":docs}
 return [{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}]

def run_hybrid_response_lab(gateway,retrieval_result,query,case_state,intent,policy,max_tokens=700):
 evidence=retrieval_result.get("evidence") or [];product=((case_state.get("products") or [""])[0]);metrics=assess_evidence(query,product,intent,evidence);decision=evaluate_document_support(metrics,policy,intent);contract=build_response_contract(decision);started=time.perf_counter();result=gateway.complete(LLMRequest(build_answer_messages(query,case_state,evidence,decision.to_dict(),contract),"technical_answer",max_tokens,0.0,None))
 return {"query":query,"retrieval":retrieval_result,"support_metrics":metrics,"evidence_decision":decision.to_dict(),"response_contract":contract,"answer_result":result.to_dict(),"total_latency_ms":round((time.perf_counter()-started)*1000,3),"production_response_changed":False}
