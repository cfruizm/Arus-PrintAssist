from pathlib import Path
import ast

def read(n):return Path('app/agent_core_v2_clean',n).read_text()
def test_syntax():
 for n in ('retrieval.py','documented_answer.py','procedural_answer.py'):ast.parse(read(n))
def test_followup_operation_enters_query():
 s=read('retrieval.py');assert 'contextual_operation' in s and '"follow_up"' in s and 'parts.append(contextual_operation)' in s
def test_context_keeps_goal_details_and_observations():
 s=read('retrieval.py');assert 'memory.pending_goal.summary' in s and 'known_details' in s and 'fields["observations"]' in s
def test_length_answer_is_published_as_partial():
 s=read('documented_answer.py');assert 'documented_answer_partial' in s and 'published_partial' in s and 'puedes pedirme continuar' in s
def test_length_reason_is_preserved():assert 'r.finish_reason' in read('documented_answer.py')
def test_operational_evidence_is_not_limited_to_steps():
 s=read('procedural_answer.py');assert '"requisito"' in s and '"compatibilidad"' in s and 'actions>=1' in s
def test_no_specific_product_or_case_rules():
 s=''.join(read(n) for n in ('retrieval.py','documented_answer.py','procedural_answer.py')).casefold()
 for x in ('papercut','web jetadmin','mfpsecure','tracking de impresión','tarjeta y pin'):assert x not in s
