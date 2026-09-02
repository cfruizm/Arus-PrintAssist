import json,re
from .models import InterpreterProposal
class QwenInterpreter:
 def __init__(self,gateway,max_tokens=220):self.gateway=gateway;self.max_tokens=max_tokens
 def interpret(self,message,state):
  from app.llm_gateway.models import LLMRequest
  system="""Interpreta un turno de soporte de impresión. Devuelve JSON con conversation_act,intent,requested_action,topic_relation,entities,facts,clarification_question,confidence,reasoning_summary. No respondas técnicamente. No inventes entidades. requested_action permitido: respond_directly,ask_clarification,retrieve,record_case_detail,record_attempt,record_attempt_result,start_escalation,continue_escalation,suspend_escalation,resume_escalation,cancel_all,out_of_scope."""
  payload=json.dumps({"message":message,"state":state.to_dict()},ensure_ascii=False)
  result=self.gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":payload}],"agent_core_v2_interpreter",self.max_tokens,0.,None))
  if not result.ok:raise RuntimeError(result.error_message or "interpreter_failed")
  text=result.text.strip();m=re.search(r"\{[\s\S]*\}",text);raw=json.loads(m.group(0) if m else text);return InterpreterProposal(**raw)
class ScriptedInterpreter:
 def __init__(self,outputs):self.outputs=list(outputs);self.i=0
 def interpret(self,message,state):r=self.outputs[self.i];self.i+=1;return InterpreterProposal(**r)
