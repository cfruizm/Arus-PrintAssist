from src.models import ConversationMemory,TurnUnderstanding,AgentDecision
from src.policy import ConversationPolicy
from src.response import NaturalResponseComposer
from src.operational_coherence import reconcile_understanding_object
from src.workflow_understanding import WorkflowInterpreter

def run():
 m=ConversationMemory();u=TurnUnderstanding("new_request","conceptual","new_topic","out_of_scope","external request",False,{},[{"type":"observation","value":"noise"}],True,"detail",True,1.0,"fixture")
 u,events=reconcile_understanding_object(u,m,None);assert u.domain_relevance=="out_of_scope" and not u.should_retrieve and not u.needs_clarification and u.case_updates==[]
 d=ConversationPolicy().decide(u,m);assert d.action=="redirect_scope"
 class G:pass
 a=NaturalResponseComposer(G()).compose("external",m,u,d);assert a.mode=="out_of_scope_closed" and "?" not in a.text and "Si quieres" not in a.text
 wi=WorkflowInterpreter(G(),96);assert wi.max_tokens==96
 import pathlib
 root=pathlib.Path(__file__).parent
 lab=(root/"lab_session.py").read_text();wf=(root/"workflow_understanding.py").read_text();doc=(root/"documented_answer.py").read_text()
 assert 'WorkflowInterpreter(_gateway(secrets_obj,s),96)' in lab
 assert '"collected_fields"' not in wf and 'max_items=6, max_chars=6200' in doc
 assert 'workflow_budget_tokens":96' in lab
 prod=(root/"response.py").read_text()+(root/"operational_coherence.py").read_text()
 for forbidden in ("presidente","shakira","waka waka","politico","celebridad"):assert forbidden not in prod.casefold()
 print({"passed":8,"failed":0,"phase":"4A.3.3"})
if __name__=="__main__":run()
