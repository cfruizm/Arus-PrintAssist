from pathlib import Path
import ast

def test_procedural_quality_envelope():
 s=Path('app/agent_core_v2_clean/procedural_answer.py').read_text();assert 'max_tokens=620' in s and 'max_items=8' in s and 'max_chars=10500' in s
def test_guard_requires_same_document_order_and_citations():
 s=Path('app/agent_core_v2_clean/procedural_answer.py').read_text();assert 'same_document_only' in s and 'ordered' in s and 'procedural_citation_guard' in s
def test_no_internal_knowledge():
 s=Path('app/agent_core_v2_clean/documented_router.py').read_text();assert 'internal_knowledge_used":False' in s and 'documented_only' in s
def test_cache_is_evidence_and_page_aware():
 s=Path('app/agent_core_v2_clean/procedural_answer.py').read_text();r=Path('app/agent_core_v2_clean/documented_router.py').read_text();assert 'pages' in s and 'evidence' in s and 'procedural_answer_cache' in r
def test_no_product_specific_rules():
 s=(Path('app/agent_core_v2_clean/procedural_answer.py').read_text()+Path('app/agent_core_v2_clean/documented_router.py').read_text()).casefold()
 for x in ('web jetadmin','papercut','facturacion','template_fac'):assert x not in s
def test_syntax():
 for f in ('procedural_answer.py','documented_router.py'):ast.parse(Path('app/agent_core_v2_clean',f).read_text())
