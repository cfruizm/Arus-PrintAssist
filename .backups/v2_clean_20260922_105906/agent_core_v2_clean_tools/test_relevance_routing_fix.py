from pathlib import Path
import sys,types
m=types.ModuleType('app.agent_core_v2_clean.models');m.AgentResponse=object;sys.modules['app.agent_core_v2_clean.models']=m
from app.agent_core_v2_clean.evidence_sufficiency import assess_procedural_evidence

def retrieval(q=.4):
 t=('Open the device page, verify login, update status and confirm access. ')*10
 return {'ok':True,'selection':{'quality':q},'evidence':[{'url':'https://x','text':t},{'url':'https://x','text':t}], 'procedural_expansion':{'ok':True,'same_document_only':True,'ordered':True}}
def test_low_relevance_never_becomes_sufficient():
 a=assess_procedural_evidence(retrieval(.4));assert a.status=='partial' and not a.generation_allowed and 'retrieval_relevance_below_generation_threshold' in a.reasons
def test_high_relevance_web_evidence_can_be_sufficient():assert assess_procedural_evidence(retrieval(.9)).status=='sufficient'
def test_router_routes_non_sufficient_to_internal():
 from pathlib import Path
 s=Path('app/agent_core_v2_clean/documented_router.py').read_text();assert 'assessment["status"]!="sufficient"' in s and 'return _internal' in s
def test_invalid_results_are_evicted_from_specialized_cache():
 s=Path('app/agent_core_v2_clean/documented_router.py').read_text()
 assert 'procedural_evidence_guard' not in s.split('def _valid_cached',1)[1].split('def _get_cache',1)[0]
 assert 'length' in s.split('def _valid_cached',1)[1].split('def _get_cache',1)[0]
def test_no_product_specific_rules():
 from pathlib import Path
 s=(Path('app/agent_core_v2_clean/evidence_sufficiency.py').read_text()+Path('app/agent_core_v2_clean/documented_router.py').read_text()).casefold()
 for x in ('papercut','subscription','pin','facturación'):assert x not in s
