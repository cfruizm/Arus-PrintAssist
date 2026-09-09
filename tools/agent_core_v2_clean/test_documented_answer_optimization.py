from pathlib import Path
import ast

def test_quality_budget_is_not_reduced():
 text=Path('app/agent_core_v2_clean/lab_session.py').read_text()
 assert 'max_tokens=260' in text and 'quality_budget_preserved' in text
 assert 'max_tokens=150' not in text

def test_evidence_envelope_preserved_with_safe_dedup_only():
 text=Path('app/agent_core_v2_clean/documented_answer.py').read_text()
 assert 'max_items=4' in text and 'max_chars=5200' in text
 assert 'exact-duplicate' in text

def test_final_answer_cache_is_versioned_and_evidence_aware():
 text=Path('app/agent_core_v2_clean/documented_answer.py').read_text()
 assert 'PROMPT_VERSION' in text and 'retrieval' in text and 'evidence' in text and 'model' in text
 session=Path('app/agent_core_v2_clean/lab_session.py').read_text()
 assert 'documented_answer_cache' in session and 'documented_answer_hits' in session

def test_goal_closes_only_after_valid_documented_answer():
 text=Path('app/agent_core_v2_clean/lab_session.py').read_text()
 block=text[text.index('if answer.mode=="documented_answer"'):]
 assert 'pending_goal.status="complete"' in block

def test_readable_sources_and_knowledge_trace():
 composer=Path('app/agent_core_v2_clean/documented_answer.py').read_text();session=Path('app/agent_core_v2_clean/lab_session.py').read_text()
 assert '**Fuentes documentales**' in composer and 'readable_sources' in composer
 assert 'documented_evidence_used' in session and 'internal_knowledge_used' in session and 'knowledge_mode' in session

def test_does_not_touch_previous_core_components():
 files=sorted(p.name for p in Path('app/agent_core_v2_clean').glob('*.py'))
 assert files==['documented_answer.py','lab_session.py']

def test_syntax():
 for name in ('documented_answer.py','lab_session.py'):ast.parse(Path('app/agent_core_v2_clean',name).read_text())
