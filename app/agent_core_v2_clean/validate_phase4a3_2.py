from src.models import ConversationMemory,TurnUnderstanding
from src.memory import apply_understanding
from src.escalation_coordinator import start,handle
from src.workflow_understanding import WorkflowUnderstanding
def w(role="ambiguous",action="none",field=None,value=None):return WorkflowUnderstanding(role,action,field,value,1.0,"fixture")
def run():
 m=ConversationMemory();m.active_subject="Service A";m.support_case.symptoms=["failure"];m.support_case.attempts=[{"action":"checked component","result":"still failing"}];start(m.escalation,m,{},"request")
 while m.escalation.status=="collecting" and m.escalation.pending_field!="client_contract_location":handle(m.escalation,"v",m,w("field_value",value="v"),{})
 key=m.escalation.pending_field;handle(m.escalation,"Acme",m,w("field_value",value="Acme"),{});assert m.escalation.fields[key]["value"]=="Acme"
 if m.escalation.status!="collecting":m.escalation.status="collecting";m.escalation.pending_field="evidence"
 handle(m.escalation,"stop",m,w("workflow_action","cancel"),{});assert m.escalation.status=="cancelled"
 handle(m.escalation,"restart",m,w("workflow_action","restart"),{});assert m.escalation.status in {"collecting","review"}
 if m.escalation.status=="review":m.escalation.status="collecting";m.escalation.pending_field="evidence"
 pending=m.escalation.pending_field;r=handle(m.escalation,"question",m,w("independent_question","suspend"),{});assert r["answer_independent"] and m.escalation.suspended_pending_field==pending
 handle(m.escalation,"resume",m,w("workflow_action","resume"),{});assert m.escalation.status in {"collecting","review"}
 m2=ConversationMemory();u=TurnUnderstanding("attempt_result","troubleshooting","same_topic","in_scope","g",False,{},[{"type":"attempted_action","value":"checked service","result":"failed"},{"type":"attempted_action","value":"checked service","result":"failed"}],False,None,True,1,"f");apply_understanding(m2,u);assert len(m2.support_case.attempts)==1 and m2.support_case.attempts[0]["result"]=="failed"
 import pathlib
 code=(pathlib.Path(__file__).parent/"escalation_coordinator.py").read_text()
 for token in ("CANCEL=","CONFIRM=","SUSPEND=","RESUME=","NO_VALUE=","re.match","startswith("):assert token not in code
 print({"passed":7,"failed":0,"phase":"4A.3.2"})
if __name__=="__main__":run()
