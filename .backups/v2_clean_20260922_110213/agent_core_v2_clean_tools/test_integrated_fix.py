from pathlib import Path
import ast
ROOT=Path('.')
def read(path):return (ROOT/path).read_text()
def test_all_files_compile():
 for f in ['app/agent_core_v2_clean/lab_session.py','app/agent_core_v2_clean/documented_router.py','app/agent_core_v2_clean/internal_knowledge.py','app/llm_gateway/gateway.py','pages/Agent_Core_V2_Clean_Lab.py']:ast.parse(read(f))
def test_new_conversation_resets_gateway_ledger():
 s=read('app/agent_core_v2_clean/lab_session.py');assert 'reset_gateway_session(s)' in s
 g=read('app/llm_gateway/gateway.py');
 for key in ['llm_gateway_calls','llm_gateway_tokens','llm_gateway_history','llm_gateway_output_ledger']:assert key in g
def test_new_store_has_unique_session_id():assert '"session_id":secrets.token_hex(12)' in read('app/agent_core_v2_clean/lab_session.py')
def test_only_valid_final_answers_are_exact_cached():
 s=read('app/agent_core_v2_clean/lab_session.py');assert 'contract and _cacheable_final(result)' in s and 'procedural_citation_guard' not in s[s.index('def _cacheable_final'):s.index('def process_message')]
def test_procedural_guard_recovers_once():
 s=read('app/agent_core_v2_clean/documented_router.py');assert 'documented_answer_validation_failed' in s and 'return result,[documented_trace,internal_trace]' in s
def test_memory_is_transactional_on_exception():assert 'store["memory"]=memory_before' in read('app/agent_core_v2_clean/lab_session.py')
def test_internal_guidance_is_contextual():
 s=read('app/agent_core_v2_clean/internal_knowledge.py');assert 'solo cuando la consulta trate sobre identidad' in s and 'Para firmware, red, colas' in s
def test_no_new_page():
 pages=list((ROOT/'pages').glob('*.py'));assert [x.name for x in pages]==['Agent_Core_V2_Clean_Lab.py']
