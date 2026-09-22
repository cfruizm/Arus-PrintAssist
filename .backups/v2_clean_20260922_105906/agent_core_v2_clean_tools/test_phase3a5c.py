import sys,types
from pathlib import Path
models=types.ModuleType('app.agent_core_v2_clean.models')
class AgentResponse: pass
models.AgentResponse=AgentResponse
sys.modules['app.agent_core_v2_clean.models']=models
from app.agent_core_v2_clean.semantic_fit import evaluate_item
from app.agent_core_v2_clean.answer_context_policy import enrich_internal_payload

def test_context_concepts_are_not_restrictive_modifiers():
 x=evaluate_item({'title':'Authentication for devices','text':'users authenticate securely on printing devices'},'configurar autenticacion segura',{'goal':'configurar autenticacion segura','intent':'procedural'}, {})
 assert x['modifier_penalty']==0 and 'concept:device' not in x['unrequested_concepts'] and 'concept:user' not in x['unrequested_concepts']
def test_cost_remains_meaning_changing_modifier():
 x=evaluate_item({'title':'About cost tracking','text':'cost tracking reduces expenses'},'tracking de impresion',{'goal':'tracking de impresion','intent':'conceptual'}, {})
 assert 'concept:cost' in x['unrequested_concepts'] and x['modifier_penalty']>0
def test_conceptual_intent_prefers_about_over_configure():
 q='tracking de impresion';f={'goal':q,'intent':'conceptual'}
 about=evaluate_item({'title':'About print tracking','text':'print tracking records jobs'},q,f,{})
 configure=evaluate_item({'title':'Configure print tracking','text':'print tracking records jobs'},q,f,{})
 assert about['intent_affinity']>configure['intent_affinity'] and about['score']>configure['score']
def test_followup_payload_contains_prior_evidence():
 c={'goal':'g','answer_mode':'x','main_text_excerpt':'prior','source_titles':['d'],'cited_ids':['R1'],'cited_evidence':[{'id':'R1','text':'fact'}]}
 p=enrich_internal_payload({'question':'follow'},c,{'user_act':'follow_up'})
 assert p['previous_answer_context']['cited_evidence'][0]['id']=='R1'
def test_prompt_preserves_confirmed_context():
 s=Path('app/agent_core_v2_clean/internal_knowledge.py').read_text()
 assert 'No contradigas detalles ya confirmados' in s and 'Distingue producto de sistema operativo' in s
