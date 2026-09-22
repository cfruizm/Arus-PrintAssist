from pathlib import Path
import ast

def test_documented_composer_requires_evidence_and_citations():
 text=Path('app/agent_core_v2_clean/documented_answer.py').read_text()
 assert '_evidence_pack' in text and '_validate_citations' in text
 assert 'documented_citation_guard' in text and 'Cada afirmación factual' in text

def test_only_conceptual_enabled_in_this_phase():
 text=Path('app/agent_core_v2_clean/lab_session.py').read_text()
 assert 'if intent!="conceptual"' in text
 assert 'Procedures remain diagnostic until multipage evidence is ready' in text

def test_cached_understanding_can_generate_answer_without_reunderstanding():
 text=Path('app/agent_core_v2_clean/lab_session.py').read_text()
 cache=text[text.index('if cached:'):text.index('allowed,reason=budget.can_call',text.index('if cached:'))]
 assert '_generate_documented' in cache
 assert 'build_agent' not in cache
 assert 'exact_turn_cache' in text

def test_retrieval_and_production_contracts_preserved():
 text=Path('app/agent_core_v2_clean/lab_session.py').read_text()
 assert 'ReadOnlyRetrieval' in text and 'production_changed":False' in text
 assert 'current_only=builder.current_only' in text

def test_modules_compile_to_ast():
 for name in ('documented_answer.py','lab_session.py'):
  ast.parse(Path('app/agent_core_v2_clean',name).read_text())
