from src.models import ConversationMemory,TurnUnderstanding,AgentDecision
from src.memory import apply_understanding
from src.agent import CleanConversationalAgent
from src.escalation_coordinator import start,sync_from_memory

class U:
 contract_valid=True;validation_error=None;normalization={};last_provider_result={"skipped":True}
 def __init__(self,obj):self.obj=obj
 def interpret(self,message,memory):return self.obj
class P:
 def __init__(self,action):self.action=action
 def decide(self,u,m):return AgentDecision(self.action,"fixture")
class R:
 last_provider_result={}
 def compose(self,*args):raise AssertionError("response composer must be skipped")

def run():
 m=ConversationMemory();m.active_subject="Existing";u=TurnUnderstanding("independent_question","unknown","independent","out_of_scope","External",True,{"subject":"External"},[],False,None,False,1,"fixture")
 result=CleanConversationalAgent(U(u),P("redirect_scope"),type("RR",(),{"last_provider_result":{},"compose":lambda self,*a:__import__("src.models",fromlist=["AgentResponse"]).AgentResponse("closed","out_of_scope_closed")})()).process("external",m)
 assert m.active_subject=="Existing" and result["conversation_entity_frame"]["transition"]=="blocked_out_of_scope"
 m2=ConversationMemory();u2=TurnUnderstanding("escalation","escalation","same_topic","in_scope","Escalate",False,{},[],False,None,False,1,"fixture",requested_workflow="start_escalation")
 r2=CleanConversationalAgent(U(u2),P("offer_escalation"),R()).process("escalate",m2);assert r2["answer"]["mode"]=="workflow_pending" and r2["provider_trace"]["response"]["skipped"]
 m3=ConversationMemory();u3=TurnUnderstanding("attempt_result","troubleshooting","same_topic","in_scope","g",False,{},[{"type":"attempted_action","value":"check service","result":"failure continues","outcome":"unchanged"}],False,None,True,1,"f")
 apply_understanding(m3,u3);assert m3.support_case.attempts[0]["outcome"]=="unchanged" and m3.support_case.attempts[0]["result"]=="failure continues"
 m3.active_subject="Service";state=m3.escalation;state.sources_consulted=[{"title":"Source A"}];sync_from_memory(state,m3,{});assert state.sources_consulted[0]["title"]=="Source A"
 import pathlib
 root=pathlib.Path(__file__).parent;doc=(root/"documented_answer.py").read_text();lab=(root/"lab_session.py").read_text();assert "already_delivered_guidance" in doc and "min(max_items,4)" in doc and "native_workflow_response_authority" in (root/"agent.py").read_text();assert "pending_goal.status" in lab
 print({"passed":5,"failed":0,"phase":"4A.3.4"})
if __name__=="__main__":run()
