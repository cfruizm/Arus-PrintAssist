from __future__ import annotations
from copy import deepcopy
from .escalation_contract import FIELDS,BY_KEY
from .escalation_export import build_export,build_text

def _set(state,key,value,source,status,turn):
 previous=deepcopy(state.fields.get(key));state.fields[key]={"value":value,"source":source,"status":status,"turn":turn}
 if key in state.unknown_fields and status!="unknown":state.unknown_fields.remove(key)
 if previous and previous.get("value")!=value:state.corrections.append({"field":key,"previous":previous.get("value"),"value":value,"turn":turn,"source":source})

def _source_rows(answer_context):
 out=[];seen=set()
 for item in (answer_context or {}).get("cited_evidence") or []:
  identity=str(item.get("source") or item.get("url") or item.get("title") or "")
  if identity and identity not in seen:seen.add(identity);out.append({"title":item.get("title"),"source":item.get("source") or item.get("url"),"page":item.get("page")})
 return out

def sync_from_memory(state,memory,answer_context=None):
 turn=int(getattr(memory,"turn_number",0) or 0);case=memory.support_case
 if getattr(memory,"active_subject",None) and not state.fields.get("product_or_service"):_set(state,"product_or_service",memory.active_subject,"conversation","confirmed",turn)
 issue="; ".join(list(case.symptoms or [])+list(case.observations or []))
 if issue and not state.fields.get("issue_description"):_set(state,"issue_description",issue,"support_case","confirmed",turn)
 if case.attempts and not state.fields.get("troubleshooting_performed"):
  values=[]
  for x in case.attempts:
   action=str(x.get("action") or "").strip();result=str(x.get("result") or "").strip()
   if action:values.append(action+(f" (resultado: {result})" if result else ""))
  if values:_set(state,"troubleshooting_performed","; ".join(values),"support_case","confirmed",turn)
 if case.affected_scope and not state.fields.get("impact_scope"):_set(state,"impact_scope",case.affected_scope,"support_case","confirmed",turn)
 state.sources_consulted=_source_rows(answer_context)

def _advance(state):
 missing=next((x for x in FIELDS if x.required and not (state.fields.get(x.key) or {}).get("value")),None)
 if not missing:missing=next((x for x in FIELDS if x.key not in state.fields),None)
 if missing:state.status="collecting";state.pending_field=missing.key
 else:state.status="review";state.pending_field=None

def start(state,memory,answer_context=None,reason="Solicitud explícita del usuario",reuse=False):
 if not reuse:
  state.fields={};state.unknown_fields=[];state.corrections=[]
 state.status="collecting";state.started_turn=getattr(memory,"turn_number",0);state.completed_turn=None;state.completion_reason=None;state.confirmed=False;state.exported=False;state.suspended_reason=None;state.suspended_pending_field=None
 state.escalation_reason={"value":reason,"source":"conversation","status":"confirmed","turn":state.started_turn};sync_from_memory(state,memory,answer_context);_advance(state);return response(state,memory)

def response(state,memory):
 if state.status=="collecting":return {"handled":True,"status":"collecting","mode":"escalation_collecting","text":BY_KEY[state.pending_field].question,"pending_field":state.pending_field}
 if state.status=="review":return {"handled":True,"status":"review","mode":"escalation_review","text":build_text(state)+"\n\nPuedes confirmar, corregir un campo o cancelar el proceso.","pending_field":None}
 if state.status=="completed":return {"handled":True,"status":"completed","mode":"escalation_completed","text":"El escalamiento quedó confirmado y cerrado. Puedes realizar una nueva consulta.","export":build_export(state,memory.conversation_id)}
 if state.status=="cancelled":return {"handled":True,"status":"cancelled","mode":"escalation_cancelled","text":"Cancelé el escalamiento y regresé a la conversación normal."}
 if state.status=="suspended":return {"handled":True,"status":"suspended","mode":"escalation_suspended","text":"Pausé el escalamiento y conservé la información recopilada."}
 return {"handled":False}

def handle_semantic(state,message,memory,understanding,answer_context=None):
 workflow=str(getattr(understanding,"requested_workflow","none") or "none");payload=str(getattr(understanding,"workflow_payload_type","none") or "none");turn=int(getattr(memory,"turn_number",0) or 0)+1
 if state.status=="completed":state.status="inactive";state.pending_field=None;return {"handled":False,"reset_after_completion":True}
 if workflow=="cancel_escalation":state.status="cancelled";state.pending_field=None;state.suspended_pending_field=None;state.completion_reason="user_cancelled";state.completed_turn=turn;return response(state,memory)
 if workflow=="suspend_escalation" or payload=="independent_question":
  if state.status in {"collecting","review"}:state.suspended_pending_field=state.pending_field;state.status="suspended";state.suspended_reason="independent_question" if payload=="independent_question" else "user_requested"
  return {"handled":False,"suspended":True,"answer_independent":payload=="independent_question"}
 if workflow=="resume_escalation":
  if state.status=="suspended":state.status="collecting";state.pending_field=state.suspended_pending_field;state.suspended_pending_field=None;state.suspended_reason=None;_advance(state);return response(state,memory)
  if state.status=="cancelled":return start(state,memory,answer_context,"Usuario reinició un escalamiento cancelado",reuse=True)
 if state.status=="suspended":return {"handled":False,"suspended":True}
 if state.status=="review":
  if workflow=="confirm_escalation":state.status="completed";state.confirmed=True;state.exported=True;state.completion_reason="user_confirmed";state.completed_turn=turn;return response(state,memory)
  if payload=="correction" and getattr(understanding,"workflow_field",None) in BY_KEY and str(getattr(understanding,"workflow_value","") or "").strip():_set(state,understanding.workflow_field,str(understanding.workflow_value).strip(),"user_correction","confirmed",turn);return response(state,memory)
  return {"handled":True,"status":"review","mode":"escalation_review","text":"El resumen está listo. Puedes confirmarlo, cancelar o indicar qué campo deseas corregir."}
 if state.status=="collecting":
  pending=state.pending_field
  if not pending:_advance(state);return response(state,memory)
  if payload=="unknown_value":
   _set(state,pending,"No disponible","user","unknown",turn)
   if pending not in state.unknown_fields:state.unknown_fields.append(pending)
  elif payload=="field_value":_set(state,pending,str(getattr(understanding,"workflow_value",None) or message).strip(),"user","confirmed",turn)
  else:return {"handled":True,"status":"collecting","mode":"escalation_collecting","text":BY_KEY[pending].question,"pending_field":pending}
  sync_from_memory(state,memory,answer_context);_advance(state);return response(state,memory)
 return {"handled":False}
