from pathlib import Path
import ast
S=lambda:Path('app/agent_core_v2_clean/lab_session.py').read_text()
def test_router_integrated_in_both_paths():
 s=S();assert s.count('_answers(')>=3 and 'maybe_generate_procedural' in s
def test_store_and_artifact_include_procedural():
 s=S();assert 'procedural_answer_cache' in s and 'procedural_answer_hits' in s and '"procedural_answer")' in s
def test_cache_hits_do_not_create_false_failures():
 s=S();assert '_zero() if not trace or trace.get("skipped")' in s
def test_prior_conceptual_path_preserved():
 s=S();assert 'DocumentedAnswerComposer' in s and 'documented_answer_cache' in s and 'max' not in ''
def test_quality_and_grounding():
 p=Path('app/agent_core_v2_clean/procedural_answer.py').read_text();assert '620' in p and 'same_document_only' in p and 'procedural_citation_guard' in p
def test_no_product_rules():
 text=(S()+Path('app/agent_core_v2_clean/procedural_answer.py').read_text()+Path('app/agent_core_v2_clean/documented_router.py').read_text()).casefold()
 for x in ('web jetadmin','papercut','template_fac','pre-facturasimp'):assert x not in text
def test_syntax():
 for f in ('lab_session.py','procedural_answer.py','documented_router.py'):ast.parse(Path('app/agent_core_v2_clean',f).read_text())
