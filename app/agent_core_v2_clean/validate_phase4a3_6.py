from src.models import ConversationMemory,TurnUnderstanding
from src.memory import apply_understanding

def run():
 m=ConversationMemory();u=TurnUnderstanding("attempt_result","troubleshooting","same_topic","in_scope","g",False,{"subject":"Platform"},[
  {"type":"attempted_action","value":"validate access","result_ok":True,"outcome_status":"unchanged"},
  {"type":"observation","value":"access still fails from all locations"}],False,None,True,1,"fixture",canonical_subject="Platform")
 apply_understanding(m,u);a=m.support_case.attempts[0]
 assert a["action"]=="validate access" and a["result"]=="access still fails from all locations" and a["outcome"]=="unchanged"
 assert m.support_case.observations==[]
 m2=ConversationMemory();u2=TurnUnderstanding("attempt_result","troubleshooting","same_topic","in_scope","g",False,{},[
  {"type":"attempted_action","value":"check service","result_detail":"failure continues","resolution_outcome":"worsened"}],False,None,True,1,"fixture")
 apply_understanding(m2,u2);assert m2.support_case.attempts[0]=={"action":"check service","result":"failure continues","outcome":"worsened"}
 import pathlib
 root=pathlib.Path(__file__).parent;lab=(root/"lab_session.py").read_text()
 assert "active_case_followup_route_recovered" in lab and "documented_trace" in lab
 assert "phase4a3_6_operational_closeout" in lab
 print({"passed":5,"failed":0,"phase":"4A.3.6"})
if __name__=="__main__":run()
