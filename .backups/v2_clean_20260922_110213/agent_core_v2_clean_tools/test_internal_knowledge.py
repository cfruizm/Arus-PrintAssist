import sys,types
m=types.ModuleType('app.agent_core_v2_clean.models')
class AgentResponse:
 def __init__(self,text,mode,knowledge_used,*args):self.text=text;self.mode=mode;self.knowledge_used=knowledge_used
m.AgentResponse=AgentResponse;sys.modules['app.agent_core_v2_clean.models']=m
from app.agent_core_v2_clean.internal_knowledge import validate_internal,WARNING

def test_separated_answer_without_citations_passes():
 text='Lo que sí indica la documentación\nContenido parcial.\nOrientación general complementaria\nVerifique condiciones.\nLímites y verificación necesaria\nConfirme con el administrador.'
 ok,d=validate_internal(text);assert ok and not d['citations_found']
def test_internal_citations_are_rejected():
 text='Lo que sí indica la documentación [R1]\nOrientación general complementaria\nA\nLímites y verificación necesaria\nB'
 assert not validate_internal(text)[0]
def test_missing_separation_is_rejected():assert not validate_internal('Pruebe estos pasos generales.')[0]
def test_warning_is_explicit():assert 'no respaldado por la documentación' in WARNING
def test_router_activates_internal_only_when_not_sufficient():
 from pathlib import Path
 s=Path('app/agent_core_v2_clean/documented_router.py').read_text();assert 'assessment["status"]!="sufficient"' in s and 'return _internal' in s
def test_no_product_specific_rules():
 from pathlib import Path
 s=(Path('app/agent_core_v2_clean/internal_knowledge.py').read_text()+Path('app/agent_core_v2_clean/documented_router.py').read_text()).casefold()
 for x in ('papercut','web jetadmin','template_fac','pre-facturasimp','facturación'):assert x not in s
def test_cache_and_telemetry_contracts():
 from pathlib import Path
 s=Path('app/agent_core_v2_clean/documented_router.py').read_text();assert 'internal_knowledge_cache' in s and 'internal_knowledge_hits' in s and 'internal_knowledge_budget_block' in s
