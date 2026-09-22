from pathlib import Path
import sys,types
models=types.ModuleType('app.agent_core_v2_clean.models')
class AgentResponse: pass
models.AgentResponse=AgentResponse
sys.modules['app.agent_core_v2_clean.models']=models
from app.agent_core_v2_clean.internal_knowledge import repair_citation_placement,validate_internal
from app.agent_core_v2_clean.semantic_fit import evaluate_item
from app.agent_core_v2_clean.telemetry import empty,add_result

def test_citations_repaired_without_llm():
 t='### Lo que indica la documentación\nDato [R1]\n### Orientación complementaria\nGuía [R1]\n### Antes de continuar\nValidar [R1]';r,changed=repair_citation_placement(t);ok,d=validate_internal(r,'stop',['R1']);assert changed and ok and '[R1]' not in r[r.find('Orientación'):]
def test_specific_modifier_penalized():
 generic=evaluate_item({'title':'About print tracking','text':'tracks print jobs'},'tracking de impresion',{'goal':'tracking de impresion'},{})
 specific=evaluate_item({'title':'About cost tracking','text':'cost tracking reduces expenses'},'tracking de impresion',{'goal':'tracking de impresion'},{})
 assert specific['modifier_penalty']>generic['modifier_penalty'] and specific['score']<generic['score']
def test_rate_limit_not_contract_or_functional_failure():
 t=empty();add_result(t,{'ok':False,'purpose':'internal','error_code':'rate_limited','usage':{},'metadata':{'request_id':'x'}});assert t['provider_failed_calls']==1 and t['contract_failed_calls']==0 and t['functional_failed_calls']==0 and 'internal' in t['by_purpose']
def test_short_clarification_prompt():
 s=Path('app/agent_core_v2_clean/response.py').read_text();assert 'do not include examples' in s and 'min(self.max_tokens,150)' in s
def test_no_product_rules():
 s=Path('app/agent_core_v2_clean/semantic_fit.py').read_text().casefold();assert 'papercut' not in s and 'mfpsecure' not in s
