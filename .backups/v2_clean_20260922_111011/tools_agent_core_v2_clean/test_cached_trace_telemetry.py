from pathlib import Path
import ast

def source():return Path('app/agent_core_v2_clean/lab_session.py').read_text()
def test_skipped_cache_trace_is_not_added_as_provider_result():
 s=source();assert 'if doc_trace and not doc_trace.get("skipped"):add_result' in s
def test_skipped_cache_turn_has_zero_failures():
 s=source();assert '"provider_failed_calls":0' in s and '"functional_failed_calls":0' in s
 assert 'if (doc_trace or {}).get("skipped") else turn_metrics' in s
def test_cached_answer_gets_knowledge_compatibility_fields():
 s=source()
 for item in ('documented_evidence_used','internal_knowledge_used','knowledge_mode'):assert f'setdefault("{item}"' in s
def test_previous_quality_and_cache_contracts_remain():
 s=source();d=Path('app/agent_core_v2_clean/documented_answer.py').read_text()
 assert 'max_tokens=260' in s and 'documented_answer_cache' in s
 assert 'PROMPT_VERSION' in d and '**Fuentes documentales**' in d
def test_syntax():ast.parse(source())
