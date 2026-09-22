from types import SimpleNamespace
import sys,types
# Tests focus on invariants of the additive runtime; repository dependencies resolve in the real app.
def test_source_declares_zero_llm_contract():
 text=open('app/agent_core_v2_clean/deterministic_lab.py').read()
 assert 'gateway' not in text and 'LLMRequest' not in text
 assert '"calls":0' in text and '"total_tokens":0' in text
def test_page_keeps_existing_modes_and_no_new_page():
 text=open('pages/Agent_Core_V2_Clean_Lab.py').read()
 assert all(x in text for x in ['"normal"','"economy"','"deterministic"'])
 assert 'process_deterministic' in text
def test_no_product_specific_rules():
 text=open('app/agent_core_v2_clean/deterministic_lab.py').read().casefold()
 assert 'papercut' not in text and 'web jetadmin' not in text and 'factur' not in text
