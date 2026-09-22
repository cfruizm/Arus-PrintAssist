from types import SimpleNamespace
from app.agent_core_v2_clean.retrieval import RetrievalQueryBuilder,ReadOnlyRetrieval

def memory(goal,details=None):
 return SimpleNamespace(pending_goal=SimpleNamespace(summary=goal,intent='procedural',known_details=details or {}),support_case=SimpleNamespace(symptoms=[],observations=[],affected_scope=None))
def test_weak_context_is_replaced_by_better_current_turn_retrieval():
 calls=[]
 def fake(q,k):
  calls.append(q)
  if len(calls)==1:return {'ok':True,'adapter':'fake','evidence':[{'title':'Previous platform manual','text':'device fleet administration','metadata':{}}]}
  return {'ok':True,'adapter':'fake','evidence':[{'title':'Billing distribution template','text':'billing distribution template cost center procedure','metadata':{'page_label':'2'}}]}
 u=SimpleNamespace(current_goal='billing distribution template',intent='procedural',goal_updates={'topic':'billing distribution template'});b=RetrievalQueryBuilder();r=ReadOnlyRetrieval(fake).search(b.build('billing distribution template',memory('billing distribution template',{'product':'stale platform'}),u),b.current_only('billing distribution template',u))
 assert len(calls)==2 and r['selection']['chosen_mode']=='current_turn_only' and r['selection']['context_contamination_avoided']
def test_strong_context_does_not_retry():
 calls=[]
 def fake(q,k):calls.append(q);return {'ok':True,'evidence':[{'title':'Fleet tool purpose','text':'fleet tool purpose and function','metadata':{}}]}
 u=SimpleNamespace(current_goal='fleet tool purpose',intent='conceptual',goal_updates={});b=RetrievalQueryBuilder();r=ReadOnlyRetrieval(fake).search(b.build('fleet tool purpose',memory('fleet tool purpose'),u),b.current_only('fleet tool purpose',u))
 assert len(calls)==1 and r['selection']['chosen_mode']=='contextual'
