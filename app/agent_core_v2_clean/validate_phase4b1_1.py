from copy import deepcopy
from app.agent_core_v2_clean.agent import CleanConversationalAgent
from app.agent_core_v2_clean.models import ConversationMemory, TurnUnderstanding, AgentResponse
from app.agent_core_v2_clean.scope_reconciler import reconcile_turn

class Understanding:
    def __init__(self,u):
        self.u=u;self.contract_valid=True;self.validation_error=None;self.normalization={};self.last_provider_result={"ok":True}
    def interpret(self,message,memory): return deepcopy(self.u)
class Policy:
    def decide(self,u,m):
        from app.agent_core_v2_clean.policy import ConversationPolicy
        return ConversationPolicy().decide(u,m)
class Response:
    def __init__(self): self.last_provider_result={"ok":True}
    def compose(self,message,m,u,d): return AgentResponse("Respuesta social natural.","natural_conversation",False)

def social_test():
    m=ConversationMemory();m.active_topic="HP SDS requirements";m.active_subject="HP SDS Monitor";m.pending_goal.summary="Review requirements";m.pending_goal.intent="requirements";m.pending_goal.status="complete";m.last_assistant_question="Previous technical question?"
    before=deepcopy(m.to_dict())
    u=TurnUnderstanding("social","social","independent","in_scope","Social exchange",True,{"operation":"initiate_conversation"},[{"type":"observation","value":"social"}],False,None,True,1.0,"social",False,None,None,"none","none")
    result=CleanConversationalAgent(Understanding(u),Policy(),Response()).process("social turn",m)
    assert result["understanding"]["should_retrieve"] is False
    assert result["understanding"]["goal_updates"]=={}
    assert result["understanding"]["case_updates"]==[]
    assert result["decision"]["action"]=="answer"
    assert m.active_topic==before["active_topic"] and m.active_subject==before["active_subject"]
    assert m.pending_goal.summary==before["pending_goal"]["summary"]
    assert m.last_assistant_question==before["last_assistant_question"]
    assert m.turn_number==before["turn_number"]+1

def reference_test():
    m=ConversationMemory();m.active_topic="HP SDS requirements";m.active_subject="HP SDS Monitor";m.pending_goal.summary="Review HP SDS Monitor requirements";m.pending_goal.intent="requirements";m.pending_goal.status="complete"
    u=TurnUnderstanding("new_request","requirements","new_topic","in_scope","Review network requirements",False,{"subject":"HP SDS Monitor","operation":"Review network and ports"},[],False,None,True,1.0,"same source",False,"HP SDS Monitor","conversation_memory","current_subject","none")
    fixed,corrections,boundary=reconcile_turn(u,m,"referential follow-up")
    assert fixed.topic_relation=="same_topic"
    assert fixed.user_act=="request_elaboration"
    assert boundary["previous_evidence_role"]=="primary"
    assert "structured_current_subject_continuity_preserved" in corrections

def source_test():
    from pathlib import Path
    root=Path(__file__).parent
    response=(root/"response.py").read_text().casefold()
    assert 'if any(x in text for x in ("gracias"' not in response
    agent=(root/"agent.py").read_text()
    assert "social_turn_operational_state_guard" in agent

if __name__=="__main__":
    social_test();reference_test();source_test();print({"passed":12,"failed":0,"phase":"4B.1.1"})
