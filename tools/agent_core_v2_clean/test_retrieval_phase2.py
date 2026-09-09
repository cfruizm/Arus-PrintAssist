from types import SimpleNamespace
from app.agent_core_v2_clean.models import ConversationMemory
from app.agent_core_v2_clean.retrieval import RetrievalQueryBuilder,ReadOnlyRetrieval

def test_query_uses_goal_atomic_details_and_case():
 m=ConversationMemory(active_topic='tema');m.pending_goal.summary='Explicar herramienta';m.pending_goal.intent='conceptual';m.pending_goal.known_details={'producto':'Herramienta X'};m.support_case.symptoms=['No responde']
 u=SimpleNamespace(current_goal='Explicar herramienta',intent='conceptual')
 q=RetrievalQueryBuilder().build('mensaje',m,u)
 assert 'Explicar herramienta' in q.text and 'Herramienta X' in q.text and 'No responde' in q.text

def test_retrieval_runs_without_llm_and_groups_documents():
 def fake(query,k):return {'ok':True,'adapter':'fake','evidence':[{'title':'Manual','url':'doc','text':'uno','metadata':{'page_label':'1'}},{'title':'Manual','url':'doc','text':'dos','metadata':{'page_label':'2'}}]}
 r=ReadOnlyRetrieval(fake,6).search(RetrievalQueryBuilder().build('x',ConversationMemory(),SimpleNamespace(current_goal='x',intent='conceptual')))
 assert r['llm_called'] is False and r['count']==2 and len(r['document_groups'])==1 and r['document_groups'][0]['pages']==['1','2']

def test_source_scores_are_not_fabricated():
 def fake(query,k):return {'ok':True,'evidence':[{'title':'A','text':'x','score':None,'metadata':{}}]}
 r=ReadOnlyRetrieval(fake).search(SimpleNamespace(text='q',to_dict=lambda:{},fingerprint='x'))
 assert r['evidence'][0]['score'] is None
