from pathlib import Path
import ast

def read(n):return Path('app/agent_core_v2_clean',n).read_text()
def test_syntax():
 for n in ('understanding.py','internal_knowledge.py','lab_session.py','procedural_answer.py'):ast.parse(read(n))
def test_conceptual_grounding_enforced():
 s=read('understanding.py');assert 'in_scope_conceptual_retrieval_enforced' in s and 'x.should_retrieve=True' in s
def test_internal_partial_visible():
 s=read('internal_knowledge.py');assert 'controlled_internal_knowledge_partial' in s and 'published_partial' in s
def test_best_attempt_selected():
 s=read('internal_knowledge.py');assert 'max(candidates,key=rank)' in s and 'selected_attempt' in s
def test_multilingual_operational_evidence():
 s=read('procedural_answer.py');assert '"requires"' in s and '"supported"' in s and '"authenticate"' in s
def test_attempts_recorded_individually():
 s=read('lab_session.py');assert 'for attempt in attempts:add_result' in s
def test_natural_response_in_turn_metrics():assert 'base.get("response")' in read('lab_session.py')
def test_no_product_rules():
 s=''.join(read(n) for n in ('understanding.py','internal_knowledge.py','lab_session.py','procedural_answer.py')).casefold()
 for x in ('papercut','web jetadmin','mfpsecure','tracking de impresión','tarjeta y pin'):assert x not in s
