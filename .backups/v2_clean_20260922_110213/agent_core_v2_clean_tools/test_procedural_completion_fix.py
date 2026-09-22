from pathlib import Path
import ast
import sys,types
m=types.ModuleType("app.agent_core_v2_clean.models")
class AgentResponse: pass
m.AgentResponse=AgentResponse
sys.modules["app.agent_core_v2_clean.models"]=m
from app.agent_core_v2_clean.procedural_answer import validate,evidence_pack

def test_markdown_bold_numbered_sections_are_valid():
 text='**1. Preparación**\nAcción [R2].\n\n**2. Ejecución**\nAcción [R3].'
 ok,cited,d=validate(text,['R2','R3'],'stop');assert ok and d['sections']==[1,2]
def test_length_finish_is_rejected_even_with_valid_citations():
 ok,_,d=validate('**1. Uno**\nA [R1].\n**2. Dos**\nB [R1].',['R1'],'length');assert not ok and not d['finish_complete']
def test_boilerplate_only_is_removed_transversally():
 r={'evidence':[{'id':'R1','text':'AVISO LEGAL INFORMACIÓN RESTRINGIDA CONTROL DE REGISTROS disposición final '*4},{'id':'R2','text':'OBJETIVO del proceso. Luego debemos abrir el archivo, validar la hoja, copiar columnas y guardar el resultado.','page':'2'}]}
 p=evidence_pack(r);assert [x['id'] for x in p]==['R2']
def test_quality_budget_increased_not_reduced():
 p=Path('app/agent_core_v2_clean/procedural_answer.py').read_text();assert 'max_tokens=900' in p and 'max_completion_tokens":900' in Path('app/agent_core_v2_clean/documented_router.py').read_text()
def test_budget_block_is_visible_not_silent():
 s=Path('app/agent_core_v2_clean/documented_router.py').read_text();assert 'generation_blocked' in s and 'procedural_budget_block' in s
def test_no_product_specific_rules():
 s=(Path('app/agent_core_v2_clean/procedural_answer.py').read_text()+Path('app/agent_core_v2_clean/documented_router.py').read_text()).casefold()
 for x in ('web jetadmin','papercut','template_fac','pre-facturasimp'):assert x not in s
def test_syntax():
 for f in ('procedural_answer.py','documented_router.py'):ast.parse(Path('app/agent_core_v2_clean',f).read_text())
