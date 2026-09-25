from __future__ import annotations
import re,unicodedata
from copy import deepcopy
from .escalation_contract import FIELDS,BY_KEY,ALIASES
from .escalation_export import build_export,build_text
NO_VALUE={'no se','no sé','desconocido','desconocida','no aplica','n/a','na','no tengo','no tengo evidencia','sin evidencia'}
CANCEL={'cancelar','cancela','salir','abortar','no escalar','cancelar escalamiento'}
CONFIRM={'confirmar','confirmo','finalizar','terminar','cerrar caso','finalizar caso','si confirmar','sí confirmar','ok'}
SUSPEND={'pausar','suspender','continuar conversando'}
RESUME={'reanudar escalamiento','continuar escalamiento','retomar escalamiento'}
def norm(v):return ' '.join(unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().casefold().split()).strip(' .,:;!?¿¡')
def _set(state,key,value,source,status,turn):
 previous=deepcopy(state.fields.get(key));state.fields[key]={'value':value,'source':source,'status':status,'turn':turn}
 if key in state.unknown_fields and status!='unknown':state.unknown_fields.remove(key)
 if previous and previous.get('value')!=value:state.corrections.append({'field':key,'previous':previous.get('value'),'value':value,'turn':turn,'source':source})
def _source_rows(answer_context):
 out=[];seen=set()
 for item in (answer_context or {}).get('cited_evidence') or []:
  identity=str(item.get('source') or item.get('url') or item.get('title') or '')
  if identity and identity not in seen:seen.add(identity);out.append({'title':item.get('title'),'source':item.get('source') or item.get('url'),'page':item.get('page')})
 return out
def sync_from_memory(state,memory,answer_context=None):
 turn=int(getattr(memory,'turn_number',0) or 0);case=memory.support_case
 if getattr(memory,'active_subject',None) and not state.fields.get('product_or_service'):_set(state,'product_or_service',memory.active_subject,'conversation','confirmed',turn)
 issue='; '.join(list(case.symptoms or [])+list(case.observations or []))
 if issue and not state.fields.get('issue_description'):_set(state,'issue_description',issue,'support_case','confirmed',turn)
 if case.attempts and not state.fields.get('troubleshooting_performed'):
  values=[]
  for x in case.attempts:
   text=str(x.get('action') or '').strip()
   if text and x.get('result'):text+=f" (resultado: {x.get('result')})"
   if text:values.append(text)
  if values:_set(state,'troubleshooting_performed','; '.join(values),'support_case','confirmed',turn)
 if case.affected_scope and not state.fields.get('impact_scope'):_set(state,'impact_scope',case.affected_scope,'support_case','confirmed',turn)
 state.sources_consulted=_source_rows(answer_context)
def _advance(state):
 missing=next((x for x in FIELDS if x.required and not (state.fields.get(x.key) or {}).get('value')),None)
 if not missing:missing=next((x for x in FIELDS if x.key not in state.fields),None)
 if missing:state.status='collecting';state.pending_field=missing.key
 else:state.status='review';state.pending_field=None
def start(state,memory,answer_context=None,reason='Solicitud explícita del usuario'):
 state.status='collecting';state.started_turn=getattr(memory,'turn_number',0);state.completion_reason=None;state.confirmed=False;state.exported=False;state.escalation_reason={'value':reason,'source':'conversation','status':'confirmed','turn':state.started_turn};sync_from_memory(state,memory,answer_context);_advance(state);return response(state,memory)
def _correction(message):
 text=norm(message);m=re.match(r'(?:corrige|cambia|actualiza)\s+(?:el campo\s+)?([^:]+?)\s+(?:a|por|:)\s+(.+)$',text)
 if not m:return None
 name,value=m.group(1).strip(),m.group(2).strip();key=next((v for k,v in ALIASES.items() if k in name),None);return (key,value) if key and value else None
def response(state,memory):
 if state.status=='collecting':return {'handled':True,'status':'collecting','mode':'escalation_collecting','text':BY_KEY[state.pending_field].question,'pending_field':state.pending_field}
 if state.status=='review':return {'handled':True,'status':'review','mode':'escalation_review','text':build_text(state)+'\n\nConfirma con "confirmar", corrige un campo o responde "cancelar".','pending_field':None}
 if state.status=='completed':return {'handled':True,'status':'completed','mode':'escalation_completed','text':'El escalamiento quedó confirmado y cerrado. Puedes realizar una nueva consulta.','export':build_export(state,memory.conversation_id)}
 if state.status=='cancelled':return {'handled':True,'status':'cancelled','mode':'escalation_cancelled','text':'Cancelé el escalamiento y regresé a la conversación normal.'}
 if state.status=='suspended':return {'handled':True,'status':'suspended','mode':'escalation_suspended','text':'Pausé el escalamiento. Puedes retomarlo cuando lo necesites.'}
 return {'handled':False}
def handle(state,message,memory,answer_context=None):
 text=norm(message);turn=int(getattr(memory,'turn_number',0) or 0)+1
 if state.status=='completed':
  state.status='inactive';state.pending_field=None
  return {'handled':False,'reset_after_completion':True}
 if text in CANCEL:
  state.status='cancelled';state.pending_field=None;state.completion_reason='user_cancelled';state.completed_turn=turn;return response(state,memory)
 if text in SUSPEND:
  state.status='suspended';state.suspended_reason='user_requested';return response(state,memory)
 if state.status=='suspended':
  if text in RESUME:state.status='collecting';state.suspended_reason=None;_advance(state);return response(state,memory)
  return {'handled':False,'suspended':True}
 if state.status=='review':
  correction=_correction(message)
  if correction:
   _set(state,correction[0],correction[1],'user_correction','confirmed',turn);return response(state,memory)
  if text in CONFIRM:
   state.status='completed';state.confirmed=True;state.exported=True;state.completion_reason='user_confirmed';state.completed_turn=turn;return response(state,memory)
  return {'handled':True,'status':'review','mode':'escalation_review','text':'El resumen está listo. Puedes confirmar, cancelar o corregir un campo, por ejemplo: "corrige cliente a ...".'}
 if state.status=='collecting':
  pending=state.pending_field
  if not pending:_advance(state);return response(state,memory)
  if text in NO_VALUE or any(text.startswith(x) for x in ('no se','no aplica','no tengo')):
   _set(state,pending,'No disponible','user','unknown',turn)
   if pending not in state.unknown_fields:state.unknown_fields.append(pending)
  elif text in {'ok','listo','entendido','gracias'}:
   return {'handled':True,'status':'collecting','mode':'escalation_collecting','text':BY_KEY[pending].question,'pending_field':pending}
  else:_set(state,pending,' '.join(str(message).split()),'user','confirmed',turn)
  sync_from_memory(state,memory,answer_context);_advance(state);return response(state,memory)
 return {'handled':False}
