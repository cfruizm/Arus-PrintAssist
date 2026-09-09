from pathlib import Path
import ast

def read(n):return Path('app/agent_core_v2_clean',n).read_text()
def test_syntax():
 for n in ('procedural_answer.py','internal_knowledge.py'):ast.parse(read(n))
def test_procedural_preserves_logic():
 s=read('procedural_answer.py')
 assert 'no conviertas alternativas (A o B) en requisitos conjuntos (A y B)' in s
 assert 'no sustituyas el método solicitado por otro parecido' in s
def test_partial_evidence_must_be_disclosed():assert 'no el procedimiento exacto solicitado' in read('procedural_answer.py')
def test_internal_does_not_make_pseudo_procedure():
 s=read('internal_knowledge.py')
 assert 'no conviertas nombres habituales de menús' in s
 assert 'No repitas como instrucción exacta' in s
def test_hypotheses_are_labeled():assert 'como hipótesis que deben confirmarse' in read('internal_knowledge.py')
def test_context_policy_preserved():assert 'solo cuando la consulta trate sobre identidad' in read('internal_knowledge.py')
def test_no_product_specific_rules():
 s=(read('procedural_answer.py')+read('internal_knowledge.py')).casefold()
 for x in ('papercut','gav tracking','epson','web jetadmin','template_fac'):assert x not in s
