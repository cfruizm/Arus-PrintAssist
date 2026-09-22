from pathlib import Path
import ast

def read(n):return Path('app/agent_core_v2_clean',n).read_text()
def test_syntax():
 for n in ('understanding.py','policy.py','documented_router.py','lab_session.py'):ast.parse(read(n))
def test_scope_contradiction_reconciled():
 s=read('understanding.py');assert 'resolvable_scope_uncertainty_to_material_clarification' in s and 'x.domain_relevance="in_scope"' in s
def test_material_question_precedes_scope_redirect():
 s=read('policy.py');a=s.index('if u.needs_clarification');b=s.index('if u.domain_relevance=="out_of_scope"');assert a<b
def test_router_requires_authorization():assert 'decision_does_not_authorize_retrieval' in read('documented_router.py')
def test_lab_central_gate():
 s=read('lab_session.py');assert s.count('decision_does_not_authorize_retrieval')>=2
def test_non_retrieval_decision_preserves_agent_answer():
 s=read('lab_session.py');block=s[s.index('def _answers'):s.index('def _trace_list')];assert 'return result,skipped,skipped' in block
def test_no_product_or_example_rules():
 s=''.join(read(n) for n in ('understanding.py','policy.py','documented_router.py','lab_session.py')).casefold()
 for x in ('papercut','web jetadmin','epson','tarjeta y pin','autenticación segura'):assert x not in s
