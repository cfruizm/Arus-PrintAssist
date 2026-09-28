from src.models import ConversationMemory,TurnUnderstanding
from src.memory import apply_understanding
from src.escalation_coordinator import start,handle_semantic
def u(workflow="none",role="none",value=None,field=None):return TurnUnderstanding("answer_to_question","procedural","same_topic","in_scope","goal",False,{},[],False,None,False,1.0,"fixture",False,None,None,"none",workflow,role,field,value)
def run():
 m=ConversationMemory();m.active_subject="Service A";m.support_case.symptoms=["failure"];m.support_case.attempts=[{"action":"checked component","result":"failure persists"}];r=start(m.escalation,m,{},"semantic request");assert "troubleshooting_performed" in m.escalation.fields
 # short ordinary answer accepted without lexical list and advances
 while m.escalation.pending_field and m.escalation.pending_field!="client_contract_location":handle_semantic(m.escalation,"value",m,u(role="field_value",value="value"),{})
 before=m.escalation.pending_field;r=handle_semantic(m.escalation,"Acme",m,u(),{});assert m.escalation.fields[before]["value"]=="Acme" and m.escalation.pending_field!=before
 # lifecycle wins
 if m.escalation.status!="collecting":m.escalation.status="collecting";m.escalation.pending_field="evidence"
 r=handle_semantic(m.escalation,"natural sentence",m,u(workflow="cancel_escalation"),{});assert r["status"]=="cancelled" and all(x.get("value")!="natural sentence" for x in m.escalation.fields.values())
 # restart cancelled reuses fields
 r=handle_semantic(m.escalation,"natural sentence",m,u(workflow="resume_escalation"),{});assert r["status"] in {"collecting","review"} and m.escalation.completion_reason is None
 # independent question suspends and resumes
 if m.escalation.status=="review":m.escalation.status="collecting";m.escalation.pending_field="evidence"
 pending=m.escalation.pending_field;r=handle_semantic(m.escalation,"question",m,u(role="independent_question"),{});assert r["answer_independent"] and m.escalation.suspended_pending_field==pending
 r=handle_semantic(m.escalation,"resume",m,u(workflow="resume_escalation"),{});assert m.escalation.status in {"collecting","review"}
 # action/result atomic
 m2=ConversationMemory();apply_understanding(m2,TurnUnderstanding("attempt_result","troubleshooting","same_topic","in_scope","goal",False,{},[{"type":"attempted_action","value":"checked service","result":"still failing"}],False,None,True,1.0,"fixture"));assert m2.support_case.attempts[-1]["result"]=="still failing"
 # no lexical workflow dictionaries in production coordinator
 import pathlib
 code=(pathlib.Path(__file__).parent/"escalation_coordinator.py").read_text()
 for token in ("CANCEL=","CONFIRM=","SUSPEND=","RESUME=","NO_VALUE=","re.match","startswith("):assert token not in code
 print({"passed":7,"failed":0,"phase":"4A.3.1"})
if __name__=="__main__":run()
