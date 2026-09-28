from __future__ import annotations
from copy import deepcopy
from .escalation_contract import FIELDS,BY_KEY
from .escalation_export import build_export,build_text

def _set(state,key,value,source,status,turn):
 previous=deepcopy(state.fields.get(key));state.fields[key]={"value":value,"source":source,"status":status,"turn":turn}
 if key in state.unknown_fields and status!="unknown":state.unknown_fields.remove(key)
 if previous and previous.get("value")!=value:state.corrections.append({"field":key,"previous":previous.get("value"),"value":value,"turn":turn,"source":source})
def _source_rows(ctx):
 out=[];seen=set()
 for item in (ctx or {}).get("cited_evidence") or []:
  identity=str(item.get("source") or item.get("url") or item.get("title") or "")
  if identity and identity not in seen:seen.add(identity);out.append({"title":item.get("title"),"source":item.get("source") or item.get("url"),"page":item.get("page")})
 return out
def sync_from_memory(state,memory,ctx=None):
 turn=int(memory.turn_number or 0);case=memory.support_case
 if memory.active_subject and not state.fields.get("product_or_service"):_set(state,"product_or_service",memory.active_subject,"conversation","confirmed",turn)
 issue="; ".join(list(case.symptoms or [])+list(case.observations or []))
 if issue and not state.fields.get("issue_description"):_set(state,"issue_description",issue,"support_case","confirmed",turn)
 if case.attempts and not state.fields.get("troubleshooting_performed"):
  rows=[]
  for x in case.attempts:
   action=str(x.get("action") or "").strip();result=str(x.get("result") or "").strip()
   if action:rows.append(action+(" (resultado: "+result+")" if result else ""))
  if rows:_set(state,"troubleshooting_performed","; ".join(rows),"support_case","confirmed",turn)
 if case.affected_scope and not state.fields.get("impact_scope"):_set(state,"impact_scope",case.affected_scope,"support_case","confirmed",turn)
 state.sources_consulted=_source_rows(ctx)
def _advance(state):
 missing=next((x for x in FIELDS if x.required and not (state.fields.get(x.key) or {}).get("value")),None) or next((x for x in FIELDS if x.key not in state.fields),None)
 if missing:state.status="collecting";state.pending_field=missing.key
 else:state.status="review";state.pending_field=None
def start(state,memory,ctx=None,reason="Solicitud explícita del usuario",reuse=False):
 if not reuse:state.fields={};state.unknown_fields=[];state.corrections=[]
 state.status="collecting";state.started_turn=memory.turn_number;state.completed_turn=None;state.completion_reason=None;state.confirmed=False;state.exported=False;state.suspended_reason=None;state.suspended_pending_field=None;state.escalation_reason={"value":reason,"source":"conversation","status":"confirmed","turn":state.started_turn};sync_from_memory(state,memory,ctx);_advance(state);return response(state,memory)
def response(state,memory):
 if state.status=="collecting":return {"handled":True,"status":"collecting","mode":"escalation_collecting","text":BY_KEY[state.pending_field].question,"pending_field":state.pending_field}
 if state.status=="review":return {"handled":True,"status":"review","mode":"escalation_review","text":build_text(state)+"\n\nPuedes confirmar, corregir un campo o cancelar el proceso.","pending_field":None}
 if state.status=="completed":return {"handled":True,"status":"completed","mode":"escalation_completed","text":"El escalamiento quedó confirmado y cerrado. Puedes realizar una nueva consulta.","export":build_export(state,memory.conversation_id)}
 if state.status=="cancelled":return {"handled":True,"status":"cancelled","mode":"escalation_cancelled","text":"Cancelé el escalamiento y regresé a la conversación normal."}
 return {"handled":False}
def handle_semantic(state,message,memory,u,ctx=None):
 workflow=str(getattr(u,"requested_workflow","none") or "none");role=str(getattr(u,"workflow_turn_role","none") or "none");turn=int(memory.turn_number or 0)+1
 if state.status=="completed":state.status="inactive";state.pending_field=None;return {"handled":False,"reset_after_completion":True}
 if workflow=="cancel_escalation":state.status="cancelled";state.pending_field=None;state.suspended_pending_field=None;state.completion_reason="user_cancelled";state.completed_turn=turn;return response(state,memory)
 if workflow=="suspend_escalation" or role=="independent_question":
  if state.status in {"collecting","review"}:state.suspended_pending_field=state.pending_field;state.status="suspended";state.suspended_reason="independent_question" if role=="independent_question" else "user_requested"
  return {"handled":False,"answer_independent":role=="independent_question","suspended":True}
 if workflow=="resume_escalation":
  if state.status=="suspended":state.status="collecting";state.pending_field=state.suspended_pending_field;state.suspended_pending_field=None;state.suspended_reason=None;_advance(state);return response(state,memory)
  if state.status=="cancelled":return start(state,memory,ctx,"Usuario reinició un escalamiento cancelado",reuse=True)
 if state.status=="suspended":return {"handled":False,"suspended":True}
 if state.status=="review":
  if workflow=="confirm_escalation":state.status="completed";state.confirmed=True;state.exported=True;state.completion_reason="user_confirmed";state.completed_turn=turn;return response(state,memory)
  if role=="correction" and getattr(u,"workflow_field",None) in BY_KEY and str(getattr(u,"workflow_value","") or "").strip():_set(state,u.workflow_field,str(u.workflow_value).strip(),"user_correction","confirmed",turn);return response(state,memory)
  return {"handled":True,"status":"review","mode":"escalation_review","text":"El resumen está listo. Puedes confirmarlo, corregir un campo o cancelar el proceso."}
 if state.status=="collecting":
  pending=state.pending_field
  if not pending:_advance(state);return response(state,memory)
  if role=="unknown_value":
   _set(state,pending,"No disponible","user","unknown",turn)
   if pending not in state.unknown_fields:state.unknown_fields.append(pending)
  else:
   # Once lifecycle and independent-question semantics have been ruled out, an ordinary reply to the last field question is the field value. This is contextual capture, not lexical matching.
   value=str(getattr(u,"workflow_value",None) or message).strip()
   if not value:return {"handled":True,"status":"collecting","mode":"escalation_clarification","text":"Necesito el dato solicitado para continuar con el escalamiento.","pending_field":pending}
   _set(state,pending,value,"user","confirmed",turn)
  sync_from_memory(state,memory,ctx);_advance(state);return response(state,memory)
 return {"handled":False}
