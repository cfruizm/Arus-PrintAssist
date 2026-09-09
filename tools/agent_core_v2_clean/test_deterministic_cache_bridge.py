from pathlib import Path
import ast

def test_no_llm_dependency():
 text=Path('app/agent_core_v2_clean/deterministic_lab.py').read_text()
 assert 'LLMRequest' not in text and '.complete(' not in text and 'gateway' not in text

def test_publishes_before_and_after_context_keys():
 text=Path('app/agent_core_v2_clean/deterministic_lab.py').read_text()
 assert 'cache[key_before]=entry' in text
 assert 'cache[_context_key(message,store["memory"])]=entry' in text

def test_cache_artifact_matches_existing_contract():
 text=Path('app/agent_core_v2_clean/deterministic_lab.py').read_text()
 for name in ('understanding','understanding_contract','goal_update_normalization','decision','answer','retrieval'):
  assert name in text
 assert 'tokens_estimate":0' in text and 'validated_without_llm":True' in text

def test_does_not_modify_prior_core_files():
 files=sorted(p.name for p in Path('app/agent_core_v2_clean').glob('*.py'))
 assert files==['deterministic_lab.py']

def test_module_compiles():
 ast.parse(Path('app/agent_core_v2_clean/deterministic_lab.py').read_text())
