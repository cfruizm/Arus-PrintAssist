from pathlib import Path
import ast

def test_page_has_web_execution_and_download():
    s=Path('pages/Agent_Core_V2_Robustness_Gate.py').read_text()
    assert 'Ejecutar gate de robustez' in s and 'Descargar reporte JSON' in s
def test_page_declares_zero_llm_and_no_production_changes():
    s=Path('pages/Agent_Core_V2_Robustness_Gate.py').read_text()
    assert 'No llama al LLM' in s and 'Producción modificada: No' in s
def test_gate_has_all_six_boundaries():
    s=Path('app/agent_core_v2_clean/robustness_gate.py').read_text()
    for case_id in ('S01','P01','I01','I02','M01','O01'): assert case_id in s
def test_gate_does_not_touch_conversation_or_provider():
    s=Path('app/agent_core_v2_clean/robustness_gate.py').read_text().casefold()
    assert 'llm_calls": 0' in s and 'conversation_changed": false' in s
    for token in ('llmgateway','complete(','process_message','session_store'): assert token not in s
def test_no_product_specific_rules():
    s=Path('app/agent_core_v2_clean/robustness_gate.py').read_text().casefold()
    for token in ('papercut','web jetadmin','template_fac','pre-facturasimp','facturación'): assert token not in s
def test_syntax():
    for f in ('app/agent_core_v2_clean/robustness_gate.py','pages/Agent_Core_V2_Robustness_Gate.py'): ast.parse(Path(f).read_text())
