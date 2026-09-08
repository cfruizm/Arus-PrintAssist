from __future__ import annotations
import json,re
class ResponseComposer:
 def __init__(self,gateway=None,max_tokens=420):self.gateway=gateway;self.max_tokens=max(280,min(440,int(max_tokens)))
 def compose_conversation(self,message,decision,state):
  if self.gateway is None:return {"mode":"conversation_pending","text":decision.clarification_question or "¿En qué puedo ayudarte?","citations":[],"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  payload={"message":message,"conversation_act":decision.conversation_act,"canonical_state":state.to_dict()}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"Respond naturally in Spanish. Use the current request and canonical state. Ask one clarification only when the request truly cannot be resolved from context."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_conversation_response",260,0.,None))
  text=res.text.strip() if res.ok else decision.clarification_question or "¿Podrías ampliar la solicitud?"
  return {"mode":"natural_conversation","text":text,"citations":[],"knowledge_used":False}
 def compose(self,query,decision,state,evidence):
  citable=list(evidence.get("citable") or []);citations=[{"id":x.get("id"),"title":x.get("title"),"url":x.get("url"),"page":(x.get("metadata") or {}).get("page_label")} for x in citable]
  if self.gateway is None:return {"mode":"grounded_pending","text":"Se recuperó evidencia para preparar la respuesta.","citations":citations,"knowledge_used":False}
  from app.llm_gateway.models import LLMRequest
  excerpts=[{"id":x.get("id"),"title":x.get("title"),"page":(x.get("metadata") or {}).get("page_label"),"text":x.get("text"),"assessment":x.get("semantic_assessment")} for x in citable]
  completeness=evidence.get("answer_completeness") or {};needs_knowledge=not bool(completeness.get("complete_enough")); exact_document=bool(completeness.get("exact_document_used"))
  policy=[
   "Answer the user's actual intent, not a generic requirements template.",
   "Use every applicable excerpt and preserve useful details. Do not collapse multiple documented items into a short paragraph.",
   "For requirements, configurations, comparisons or multi-part requests, organize the answer with headings and bullet points. List all documented operating systems, runtimes, network conditions, accounts, ports, dependencies, exceptions and validation steps that are present.",
   "For procedures, preserve the sequence as numbered steps and include prerequisites and validations.",
   "If exact_document_continuation is true, exhaust the document evidence first and do not add generic model knowledge unless a material gap remains. If evidence is partial or absent, provide useful model knowledge under the exact heading 'Orientación complementaria, no confirmada por las fuentes recuperadas'.",
   "Complementary knowledge may explain likely concepts, safe checks and possible navigation. Never claim that exact internal workflows, credentials, values or vendor-specific paths are confirmed.",
   "Do not merely say information is unavailable. Keep the limitation to one sentence.",
   "Do not expose internal terms such as approved documentation, approved excerpt, evidence judge, claims or pipeline.",
   "Do not mix the previous product or process into a new topic unless it is explicitly relevant to the current request.",
   "Write a complete but concise Spanish answer. Prefer bullets over dense prose."
  ]
  payload={"request":query,"intent":decision.intent,"active_topic":state.active_topic.to_dict() if hasattr(state.active_topic,"to_dict") else {},"evidence":excerpts,"evidence_is_partial":needs_knowledge,"exact_document_continuation":exact_document,"policy":policy}
  res=self.gateway.complete(LLMRequest([{"role":"system","content":"You are a natural technical support assistant. Documentation has priority, but partial documentation must be supplemented with clearly labeled general model knowledge. Produce only the user-facing answer."},{"role":"user","content":json.dumps(payload,ensure_ascii=False,default=str)}],"agent_core_v2_answer",self.max_tokens,0.,None))
  if not res.ok:
   documented=[str(x.get("text") or "").strip() for x in citable[:4] if str(x.get("text") or "").strip()]
   text="Encontré documentación aplicable, pero el proveedor no permitió completar la redacción en este momento." + ("\n\nFragmentos documentales recuperados:\n\n"+"\n\n".join(documented) if documented else "")
   return {"mode":"document_preserving_fallback","text":text,"citations":citations,"knowledge_used":False,"error_code":getattr(res,"error_code",None),"retryable":getattr(res,"error_code",None)=="rate_limit_exceeded"}
  text=res.text.strip();marker="Orientación complementaria, no confirmada por las fuentes recuperadas";knowledge_used=marker.casefold() in text.casefold()
  mode="grounded_plus_guarded_knowledge" if citable and knowledge_used else ("guarded_internal_knowledge" if knowledge_used else "grounded")
  return {"mode":mode,"text":text,"citations":citations,"knowledge_used":knowledge_used,"internal_knowledge_used":knowledge_used,"internal_knowledge_warning_shown":knowledge_used,"unassessed_sources":[x.get("id") for x in evidence.get("unassessed") or []],"provider":res.provider,"model":res.model,"usage":res.usage,"finish_reason":res.finish_reason}
