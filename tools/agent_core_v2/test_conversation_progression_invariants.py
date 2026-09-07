from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app.agent_core_v2.interpreter import ScriptedInterpreter
from app.agent_core_v2.models import ConversationState
from app.agent_core_v2.decision import DecisionReconciler
from app.agent_core_v2.evidence_judge import SemanticEvidenceJudge
from app.agent_core_v2.response import ResponseComposer
class JudgeResult:
 ok=True;text='{"assessments":[]}';finish_reason='stop';error_message=None
 def to_dict(self):return {"ok":True,"text":self.text}
class Gateway:
 def complete(self,*args):return JudgeResult()
def main():
 state=ConversationState();state.active_topic.intent="conceptual"
 raw={"conversation_act":"clarification","intent":"procedural","topic_relation":"same_topic","entities":[],"facts":[],"requires_documents":False,"escalation_action":"none","confidence":.95,"reasoning_summary":"clear how-to request"}
 proposal=ScriptedInterpreter([raw]).interpret("generic how-to",state)
 decision=DecisionReconciler().reconcile(proposal,state,[])
 assert proposal.conversation_act=="technical_request" and decision.action=="retrieve"
 candidate={"id":"S1","title":"Guide","text":"excerpt","metadata":{}}
 judged=SemanticEvidenceJudge(Gateway(),300,3).evaluate("request","procedural",[],[candidate])
 assert judged["assessments"]==[]
 state.escalation.status="collecting";state.escalation.pending_field=None
 escalation=type("D",(),{"intent":"escalation","clarification_question":None})()
 answer=ResponseComposer(None,400).compose_conversation("escalate",escalation,state)
 assert answer["mode"]=="deterministic_escalation_acknowledgement"
 print("conversation progression invariants passed")
if __name__=="__main__":main()
