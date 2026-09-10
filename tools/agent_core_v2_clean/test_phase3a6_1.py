from app.agent_core_v2_clean.models import ConversationMemory,TurnUnderstanding
from app.agent_core_v2_clean.memory import apply_understanding
from app.agent_core_v2_clean.semantic_contract import build_response_contract
from app.agent_core_v2_clean.internal_knowledge import authorized_evidence

def test_user_fact_is_confirmed():
 m=ConversationMemory();u=TurnUnderstanding('answer_to_question','procedural','same_topic','in_scope','Configure',False,{'platform':'Any Platform'},[],False,None,True,.9,'ok');m.last_assistant_question='Which?';apply_understanding(m,u);c=build_response_contract(m,u,{});assert c['confirmed_facts'][0]['value']=='Any Platform'
def test_previous_evidence_is_authorized_and_remapped():
 r={'generation_evidence':[{'id':'R1','source':'a','text':'current'}],'_answer_context':{'cited_evidence':[{'id':'R9','source':'b','text':'prior'}]}};e=authorized_evidence(r);assert [x['id'] for x in e]==['R1','R2'];assert len({x['stable_id'] for x in e})==2
def test_no_retry_prompt_loop():
 import inspect,app.agent_core_v2_clean.internal_knowledge as m
 s=inspect.getsource(m.ControlledInternalKnowledgeComposer.compose);assert 'second=' not in s and 'RETRY_SYSTEM' not in s
