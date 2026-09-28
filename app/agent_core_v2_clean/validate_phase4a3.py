from src.models import ConversationMemory,TurnUnderstanding
from src.memory import apply_understanding
from src.escalation_coordinator import start,handle_semantic

def u(workflow="none",payload="none",value=None,field=None,inquiry=False):
 return TurnUnderstanding("answer_to_question","procedural","same_topic","in_scope","current support case",False,{},[],False,None,False,1.0,"fixture",False,None,None,"none",workflow,payload,field,value,inquiry)
def run():
 m=ConversationMemory();m.active_subject="Service A";m.support_case.symptoms=["service unavailable"];m.support_case.attempts=[{"action":"validated shared component","result":"failure persists"}]
 r=start(m.escalation,m,{},"semantic request");assert r["status"]=="collecting";assert "troubleshooting_performed" in m.escalation.fields
 # lifecycle semantics always outrank pending field capture
 r=handle_semantic(m.escalation,"free natural language",m,u("cancel_escalation"),{});assert r["status"]=="cancelled";assert all(x.get("value")!="free natural language" for x in m.escalation.fields.values())
 # cancelled workflow restarts by reusing valid fields, not by inventing a ticket
 r=handle_semantic(m.escalation,"free natural language",m,u("resume_escalation"),{});assert r["status"] in {"collecting","review"};assert m.escalation.completion_reason is None
 # independent question suspends and preserves exact pending field
 pending=m.escalation.pending_field;r=handle_semantic(m.escalation,"free natural language",m,u(payload="independent_question"),{});assert r["answer_independent"] and m.escalation.status=="suspended" and m.escalation.suspended_pending_field==pending
 r=handle_semantic(m.escalation,"free natural language",m,u("resume_escalation"),{});assert m.escalation.status in {"collecting","review"}
 # unavailable field is semantic, not lexical
 if m.escalation.status=="collecting":
  key=m.escalation.pending_field;handle_semantic(m.escalation,"arbitrary",m,u(payload="unknown_value"),{});assert m.escalation.fields[key]["status"]=="unknown"
 # correction is canonical and structured
 m.escalation.status="review";handle_semantic(m.escalation,"arbitrary",m,u(payload="correction",field="impact_scope",value="updated scope"),{});assert m.escalation.fields["impact_scope"]["value"]=="updated scope"
 # action and result persist atomically
 m2=ConversationMemory();apply_understanding(m2,TurnUnderstanding("attempt_result","troubleshooting","same_topic","in_scope","diagnose",False,{},[{"type":"attempted_action","value":"checked component","result":"issue remains"}],False,None,True,1.0,"fixture"));assert m2.support_case.attempts[-1]=={"action":"checked component","result":"issue remains"}
 # production coordinator has no lexical action dictionaries or phrase rules
 import pathlib
 code=(pathlib.Path(__file__).parent/"escalation_coordinator.py").read_text()
 for forbidden in ("CANCEL=","CONFIRM=","SUSPEND=","RESUME=","NO_VALUE=","re.match","startswith("):
  assert forbidden not in code
 print({"passed":9,"failed":0,"phase":"4A.3"})
if __name__=="__main__":run()
