import sys,types
m=types.ModuleType('app.agent_core_v2_clean.models');m.AgentResponse=object;sys.modules['app.agent_core_v2_clean.models']=m
from app.agent_core_v2_clean.budget import BudgetPolicy
from app.agent_core_v2_clean.evidence_sufficiency import assess_procedural_evidence
from app.agent_core_v2_clean.internal_knowledge import validate_internal

def test_session_budgets_are_larger():assert BudgetPolicy.for_mode('economy').max_session_tokens==7000 and BudgetPolicy.for_mode('normal').max_session_tokens==14000
def test_reserve_is_preserved():assert not BudgetPolicy.for_mode('economy').can_call({'calls':1,'total_tokens':6300},1)[0]
def test_web_docs_without_pages_use_chunks():
 t=('Configure the field, verify the user, save and confirm the result. ')*10;r={'ok':True,'evidence':[{'id':'R1','url':'https://x/a','text':t},{'id':'R2','url':'https://x/a','text':t}], 'procedural_expansion':{'ok':True,'same_document_only':True,'ordered':True}}
 a=assess_procedural_evidence(r);assert a.status=='sufficient' and a.coverage_basis=='chunks_without_pages'
def test_truncated_internal_answer_is_rejected():
 t='Lo que sí indica la documentación [R1]\nA\nOrientación general complementaria\nB\nLímites y verificación necesaria\nC';assert not validate_internal(t,'length',['R1'])[0]
def test_internal_citations_only_allowed_in_documented_section():
 good='Lo que sí indica la documentación [R1]\nA\nOrientación general complementaria\nB\nLímites y verificación necesaria\nC';bad=good+' [R1]';assert validate_internal(good,'stop',['R1'])[0] and not validate_internal(bad,'stop',['R1'])[0]
def test_no_product_rules():
 from pathlib import Path
 s=''.join(Path('app/agent_core_v2_clean',f).read_text().casefold() for f in ('budget.py','evidence_sufficiency.py','internal_knowledge.py'))
 for x in ('papercut','template_fac','pre-facturasimp','facturación'):assert x not in s
