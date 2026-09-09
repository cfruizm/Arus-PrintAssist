from pathlib import Path
import ast

def text(name):return Path('app/agent_core_v2_clean',name).read_text()
def test_syntax():
 for n in ('documented_router.py','internal_knowledge.py','procedural_answer.py'):ast.parse(text(n))
def test_internal_path_has_no_recursive_recovery():
 s=text('documented_router.py');internal=s[s.index('def _internal'):s.index('def maybe_generate_procedural')]
 assert 'procedural_recovery' not in internal and 'documented_answer_validation_failed' not in internal
def test_procedural_path_recovers_once():
 s=text('documented_router.py');proc=s[s.index('def maybe_generate_procedural'):]
 assert proc.count('procedural_recovery')==1 and 'return result,[documented_trace,internal_trace]' in proc
def test_partial_evidence_calls_internal_directly():
 s=text('documented_router.py')
 assert 'if assessment["status"]!="sufficient":return _internal' in s
def test_internal_retries_any_validation_failure():
 s=text('internal_knowledge.py')
 assert "if res.ok and not ok:" in s
 assert "not self.validation.get('finish_complete')" not in s
def test_retry_explicitly_repairs_citations():
 s=text('internal_knowledge.py')
 assert 'elimina todas las citas de las secciones 2 y 3' in s
def test_context_policy_preserved():
 s=text('internal_knowledge.py')
 assert 'solo cuando la consulta trate sobre identidad' in s
def test_no_product_rules():
 s=(text('documented_router.py')+text('internal_knowledge.py')).casefold()
 for word in ('papercut','web jetadmin','epson','template_fac'):assert word not in s
