from types import SimpleNamespace
from app.agent_core_v2_clean.retrieval import RetrievalQueryBuilder,ReadOnlyRetrieval
def memory():return SimpleNamespace(pending_goal=SimpleNamespace(summary='Explicar herramienta',intent='conceptual',known_details={'producto':'Herramienta X'}),support_case=SimpleNamespace(symptoms=['No responde'],observations=[],affected_scope=None))
def test_query_uses_context():
 q=RetrievalQueryBuilder().build('mensaje',memory(),SimpleNamespace(current_goal='Explicar herramienta',intent='conceptual'))
 assert 'Herramienta X' in q.text and 'No responde' in q.text
def test_grouping_and_no_llm():
 def fake(q,k):return {'ok':True,'adapter':'fake','evidence':[{'title':'Manual','url':'doc','text':'uno','metadata':{'page_label':'1'}},{'title':'Manual','url':'doc','text':'dos','metadata':{'page_label':'2'}}]}
 q=SimpleNamespace(text='manual',fields={'current_message':'manual'},to_dict=lambda:{},fingerprint='x');r=ReadOnlyRetrieval(fake).search(q)
 assert not r['llm_called'] and len(r['document_groups'])==1 and r['document_groups'][0]['pages']==['1','2']
