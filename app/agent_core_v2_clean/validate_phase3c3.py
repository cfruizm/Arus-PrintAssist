from copy import deepcopy
from src.models import ConversationMemory, TurnUnderstanding, AgentResponse
from src.agent import CleanConversationalAgent
from src.scope_boundary import reconcile_scope_boundary

class U:
 contract_valid=True;validation_error=None;normalization={};last_provider_result={"skipped":True}
 def __init__(self, value): self.value=value
 def interpret(self,message,memory): return deepcopy(self.value)
class R:
 last_provider_result={"skipped":True}
 def compose(self,message,memory,u,d):
  return AgentResponse("Ese tema está fuera de mi alcance de soporte de impresión. Si quieres, continuamos con el caso técnico.","out_of_scope")
class P:
 def decide(self,u,m):
  from src.policy import ConversationPolicy
  return ConversationPolicy().decide(u,m)

def turn(subject="External subject"):
 return TurnUnderstanding("new_request","conceptual","new_topic","uncertain","Identify external subject",True,{"subject":subject},[],False,None,True,.98,"independent request",False,subject,"current_message","none")
def run():
 m=ConversationMemory();m.active_topic="Explain HP SDS";m.pending_goal.summary="Explain HP SDS";m.pending_goal.intent="conceptual";m.pending_goal.status="complete";m.pending_goal.known_details={"subject":"HP SDS"};m.active_subject="HP SDS";before=deepcopy(m.to_dict())
 result=CleanConversationalAgent(U(turn()),P(),R()).process("External question",m)
 assert result["decision"]["action"]=="redirect_scope"
 assert result["retrieval"]["enabled"] is False and result["retrieval"]["skipped_reason"]=="domain_boundary_pre_retrieval"
 assert result["answer"]["mode"]=="out_of_scope"
 assert result["state_after"]["active_topic"]==before["active_topic"]
 assert result["state_after"]["active_subject"]==before["active_subject"]
 assert result["state_after"]["pending_goal"]["summary"]==before["pending_goal"]["summary"]
 assert result["conversation_entity_frame"]["skipped"] is True
 assert result["scope_boundary"]["final_relevance"]=="out_of_scope"
 continuation=TurnUnderstanding("follow_up","conceptual","same_topic","uncertain","Explain HP SDS purpose",False,{"subject":"HP SDS"},[],False,None,True,.9,"continuation",False,"HP SDS","conversation_memory","current_subject")
 continuation,gate=reconcile_scope_boundary(continuation,m)
 assert not gate.blocked_before_retrieval and continuation.domain_relevance=="uncertain"
 print({"passed":9,"failed":0,"phase":"3C.3"})
if __name__=="__main__":run()
