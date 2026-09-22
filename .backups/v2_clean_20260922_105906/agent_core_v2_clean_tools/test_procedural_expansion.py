from types import SimpleNamespace
import sys,types
from app.agent_core_v2_clean.retrieval import ReadOnlyRetrieval,RetrievalQuery

def evidence(title,source,page,text):return {'title':title,'source':source,'url':source,'text':text,'metadata':{'source':source,'page_label':str(page),'title':title}}
def install_expander(items):
 m=types.ModuleType('app.integration.document_expansion_adapter');m.retrieve_same_document=lambda q,s,k:{'ok':True,'adapter':'fake.same_document','evidence':items,'errors':[]};sys.modules['app.integration.document_expansion_adapter']=m
def test_procedural_expands_same_document_and_orders_pages():
 seed=evidence('Procedure','doc-a',3,'procedure step three')
 def initial(q,k):return {'ok':True,'adapter':'fake','evidence':[seed]}
 install_expander([evidence('Procedure','doc-a',4,'procedure step four'),evidence('Procedure','doc-a',2,'procedure step two')])
 q=RetrievalQuery('procedure',{'intent':'procedural','current_message':'procedure'},'fp');r=ReadOnlyRetrieval(initial).search(q)
 assert r['procedural_expansion']['llm_called'] is False
 assert r['procedural_expansion']['same_document_only']
 assert r['procedural_expansion']['pages']==['2','3','4']
 assert len(r['document_groups'])==1

def test_conceptual_behavior_is_unchanged():
 def initial(q,k):return {'ok':True,'adapter':'fake','evidence':[evidence('Guide','doc',1,'tool definition and purpose')]}
 q=RetrievalQuery('tool purpose',{'intent':'conceptual','current_message':'tool purpose'},'fp');r=ReadOnlyRetrieval(initial).search(q)
 assert r['count']==1 and not r['procedural_expansion']['enabled']

def test_expansion_failure_is_fail_soft():
 m=types.ModuleType('app.integration.document_expansion_adapter');m.retrieve_same_document=lambda q,s,k:{'ok':False,'evidence':[],'errors':['x']};sys.modules['app.integration.document_expansion_adapter']=m
 def initial(q,k):return {'ok':True,'evidence':[evidence('Procedure','doc',2,'procedure content')]}
 q=RetrievalQuery('procedure',{'intent':'procedural','current_message':'procedure'},'fp');r=ReadOnlyRetrieval(initial).search(q)
 assert r['count']>=1 and r['ok'] and r['procedural_expansion']['attempted']

def test_no_product_specific_rules():
 text=open('app/agent_core_v2_clean/retrieval.py').read().casefold()+open('app/integration/document_expansion_adapter.py').read().casefold()
 for word in ('web jetadmin','papercut','facturacion','template'):assert word not in text
