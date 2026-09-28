from src.models import ConversationMemory,TurnUnderstanding
from src.memory import apply_understanding
from src.escalation_coordinator import start
from src.documented_answer import _compact_followup_checks
from src.semantic_fit import capture_answer_context

def run():
 m=ConversationMemory();u=TurnUnderstanding("new_request","troubleshooting","new_topic","in_scope","g",False,{"subject":"Printer Platform"},[{"type":"symptom","value":"failure"},{"type":"scope","value":"two users"}],False,None,True,1,"f",canonical_subject="Printer Platform")
 apply_understanding(m,u);assert m.support_case.subject=="Printer Platform" and m.support_case.affected_scope=="two users"
 m.active_subject="Side Topic";start(m.escalation,m,{},"request");assert m.escalation.fields["product_or_service"]["value"]=="Printer Platform"
 text="Intro\n1. First [R1]\n2. Second [R1]\n3. Third [R1]\n4. Fourth [R1]"
 compact=_compact_followup_checks(text,{"topic_relation":"same_topic","user_act":"new_request"});assert "4. Fourth" not in compact and "3. Third" in compact
 result={"answer":{"text":"1. First check [R1]\n2. Second check [R1]","mode":"documented_answer","finish_reason":"stop"},"retrieval":{"evidence":[{"id":"R1","title":"Guide","text":"evidence"}]},"understanding":{"current_goal":"g"}}
 ctx=capture_answer_context(result);assert len(ctx["delivered_guidance"])==2
 import pathlib
 root=pathlib.Path(__file__).parent;lab=(root/"lab_session.py").read_text();doc=(root/"documented_answer.py").read_text();assert "phase4a3_5_followup_case_identity_recovery" in lab and "already_delivered_guidance" in doc
 print({"passed":5,"failed":0,"phase":"4A.3.5"})
if __name__=="__main__":run()
