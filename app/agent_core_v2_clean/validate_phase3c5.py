from pathlib import Path
from src.models import ConversationMemory,TurnUnderstanding
from src.retrieval import RetrievalQueryBuilder,ReadOnlyRetrieval
from src.unified_evidence_authority import apply_unified_evidence_verdict
from src.topic_boundary import infer_topic_boundary
from src.internal_knowledge import SYSTEM

def row(title,text,score=.4):return {"id":"R1","title":title,"text":text,"source":title,"metadata":{},"semantic_fit":{"score":score}}
def run():
 m=ConversationMemory();m.active_topic="Diagnose unavailable output device";m.active_subject="output device";m.pending_goal.summary=m.active_topic;m.pending_goal.known_details={"subject":"output device"};m.support_case.status="diagnosing";m.support_case.symptoms=["unavailable"]
 u={"intent":"procedural","user_act":"request_elaboration","topic_relation":"same_topic","current_goal":"Provide detailed validations","canonical_subject":"output device","goal_updates":{"subject":"output device"}}
 b=infer_topic_boundary(m.to_dict(),u);assert b.relation=="same_topic_refinement"
 retrieval={"query":{"fields":{"goal":"Validate unavailable output device","current_message":"Give detailed validations","symptoms":["unavailable"],"observations":["one workstation"]}},"diagnostic_evidence":[row("Enable Remote Upload Workflow","Enable the remote upload workflow in the administration console.")],"semantic_fit":{}}
 out=apply_unified_evidence_verdict(retrieval,"Give detailed validations",{"intent":"procedural","canonical_subject":"output device","current_goal":"Validate unavailable output device","goal_updates":{"subject":"output device"}})
 assert not out["evidence_verdict"]["accepted"] and out["evidence_verdict"]["reason"] in {"missing_requested_operation","unconfirmed_mechanism_for_active_case"} and not out["evidence_verdict"]["active_case_alignment"]
 retrieval2={"query":{"fields":{"goal":"Validate unavailable output device service","current_message":"Validate service","symptoms":["service unavailable"],"observations":[]}},"diagnostic_evidence":[row("Validate unavailable device service","Check the unavailable device service and restart it, then verify status.",.8)],"semantic_fit":{}}
 out2=apply_unified_evidence_verdict(retrieval2,"Validate unavailable device service",{"intent":"procedural","canonical_subject":"output device","current_goal":"Validate unavailable device service","goal_updates":{"subject":"output device"}})
 assert out2["evidence_verdict"]["accepted"]
 m2=ConversationMemory();m2.pending_goal.summary="Provide account credential self-service";m2.pending_goal.intent="procedural";m2.pending_goal.known_details={"subject":"Platform A"};m2.active_subject="Previous Device";m2.support_case.status="diagnosing";m2.support_case.symptoms=["old failure"]
 uu=TurnUnderstanding("request_elaboration","procedural","same_topic","in_scope","Provide account credential self-service",False,{"subject":"Platform A"},[],False,None,True,1,"fixture",False,"Platform A","conversation_memory","current_subject")
 q=RetrievalQueryBuilder().build("How can the user manage it?",m2,uu);assert q.fields["symptoms"]==[] and not q.fields["case_context_included"]
 calls=[]
 def fake(query,k):calls.append((query,k));return {"ok":True,"evidence":[]}
 ro=ReadOnlyRetrieval(fake,k=6);cur=RetrievalQueryBuilder().current_only("How can the user manage it?",uu);ro.search(q,cur)
 assert len(calls)==3 and calls[-1][1]==10 and "Platform A" in calls[-1][0]
 assert "No inventes menús, rutas, botones, campos, URLs" in SYSTEM
 policy=(Path(__file__).with_name('retrieval.py').read_text()+Path(__file__).with_name('unified_evidence_authority.py').read_text())
 for forbidden in ("Web Print","Print Evolve","PaperCut","My PIN"):assert forbidden not in policy
 print({"passed":9,"failed":0,"phase":"3C.5"})
if __name__=="__main__":run()
