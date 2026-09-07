from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app.agent_core_v2.interpreter import ScriptedInterpreter
from app.agent_core_v2.models import ConversationState
from app.agent_core_v2.entity_resolver import EntityResolver
from app.agent_core_v2.decision import DecisionReconciler
from app.agent_core_v2.transitions import TransitionEngine

def main():
 raw={"conversation_act":"clarification","intent":"troubleshooting","topic_relation":"new_topic","entities":[{"type":"product","name":"HP SDS"}],"facts":[{"key":"symptom","value":"servicio degradado"},{"key":"affected_scope","value":"multiples dispositivos"}],"requires_documents":True,"escalation_action":"none","confidence":.95,"reasoning_summary":"technical failure requiring documentation"}
 state=ConversationState(); proposal=ScriptedInterpreter([raw]).interpret("Caso tecnico",state)
 assert proposal.conversation_act=="technical_request" and proposal.requested_action=="retrieve"
 assert [x["type"] for x in proposal.facts]==["symptom","affected_scope"]
 entities=EntityResolver("app.domain_registry_v1").resolve("HP SDS",proposal.entities)
 assert entities[0].canonical_id=="hp_sds" and entities[0].canonical_name=="HP Smart Device Services"
 decision=DecisionReconciler().reconcile(proposal,state,entities)
 assert decision.action=="retrieve" and decision.requires_retrieval
 state.turn_number=1;TransitionEngine().apply(state,decision,increment_turn=False)
 assert state.technical_case.status=="diagnosing"
 assert state.technical_case.symptoms==["servicio degradado"]
 assert state.technical_case.affected_scope=="multiples dispositivos"
 # Generic secondary defense: coherent technical evidence cannot be blocked by contradictory clarification.
 raw2={**raw,"requires_documents":False,"entities":[],"facts":[{"type":"symptom","value":"degraded behavior"}]}
 proposal2=ScriptedInterpreter([raw2]).interpret("Another technical case",ConversationState())
 decision2=DecisionReconciler().reconcile(proposal2,ConversationState(),[])
 assert decision2.action=="retrieve"
 print("contract normalization and reconciliation tests passed")
if __name__=="__main__":main()
