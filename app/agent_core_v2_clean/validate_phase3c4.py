from copy import deepcopy
from src.models import ConversationMemory,TurnUnderstanding,AgentResponse
from src.agent import CleanConversationalAgent
from src.topic_boundary import infer_topic_boundary
from src.unified_evidence_authority import apply_unified_evidence_verdict
from src.internal_knowledge import SYSTEM
class U:
 contract_valid=True;validation_error=None;normalization={};last_provider_result={"skipped":True}
 def __init__(self,v):self.v=v
 def interpret(self,message,memory):return deepcopy(self.v)
class R:
 last_provider_result={"skipped":True}
 def compose(self,message,memory,u,d):return AgentResponse("Ese tema está fuera de mi alcance de soporte de impresión. Si quieres, continuamos con el caso técnico.","out_of_scope")
class P:
 def decide(self,u,m):
  from src.policy import ConversationPolicy
  return ConversationPolicy().decide(u,m)
def run():
 # Scope pre-retrieval and state preservation.
 m=ConversationMemory();m.active_topic="Explain HP SDS";m.active_subject="HP SDS";m.pending_goal.summary="Explain HP SDS";m.pending_goal.status="complete";before=m.to_dict()
 ext=TurnUnderstanding("new_request","conceptual","new_topic","uncertain","Identify external subject",True,{"subject":"External"},[],False,None,True,.9,"fixture",False,"External","current_message","none")
 r=CleanConversationalAgent(U(ext),P(),R()).process("External",m)
 assert r["decision"]["action"]=="redirect_scope" and not r["retrieval"]["enabled"]
 assert r["state_after"]["active_topic"]==before["active_topic"] and r["state_after"]["active_subject"]==before["active_subject"]
 # Active troubleshooting case, same subject, procedural expansion is continuity.
 state=ConversationMemory();state.active_topic="Troubleshoot unavailable printer";state.active_subject="print device";state.pending_goal.summary="Troubleshoot unavailable printer";state.pending_goal.known_details={"subject":"print device"};state.support_case.status="diagnosing"
 u={"intent":"procedural","user_act":"request_elaboration","topic_relation":"same_topic","current_goal":"Provide detailed procedure for the proposed validations","goal_updates":{"subject":"print device"}}
 b=infer_topic_boundary(state.to_dict(),u)
 assert b.relation=="same_topic_refinement" and b.reason=="active_case_procedural_expansion"
 # Procedure evidence must cover a distinctive requested operation, not only product/authentication.
 retrieval={"diagnostic_evidence":[{"id":"R1","title":"Authenticating users in Sample Product","text":"Users authenticate and link a client to the portal.","source":"auth","metadata":{"product":"sample_product"},"semantic_fit":{"score":.8}}],"semantic_fit":{}}
 pu={"intent":"procedural","canonical_subject":"Sample Product","current_goal":"Self-manage print PIN in Sample Product","goal_updates":{"subject":"Sample Product"}}
 out=apply_unified_evidence_verdict(retrieval,"How can a user self-manage the print PIN?",pu)
 assert not out["evidence_verdict"]["accepted"] and out["evidence_verdict"]["reason"]=="missing_requested_operation"
 # Exact operational evidence remains authorized.
 retrieval2={"diagnostic_evidence":[{"id":"R1","title":"Assign PIN in Sample Product","text":"Select the user, enter the PIN and update the record.","source":"pin","metadata":{"product":"sample_product"},"semantic_fit":{"score":.8}}],"semantic_fit":{}}
 out2=apply_unified_evidence_verdict(retrieval2,"How do I assign a PIN to a user?",{"intent":"procedural","canonical_subject":"Sample Product","current_goal":"Assign PIN","goal_updates":{"subject":"Sample Product"}})
 assert out2["evidence_verdict"]["accepted"]
 assert "orientación general detallada basada en conocimiento interno" in SYSTEM
 print({"passed":8,"failed":0,"phase":"3C.4"})
if __name__=="__main__":run()
