from pathlib import Path
import ast

def test_selected_trace_preserves_gateway_contract():
 s=Path('app/agent_core_v2_clean/internal_knowledge.py').read_text()
 assert 'selected=res.to_dict()' in s and "selected['attempts']" in s
def test_retry_usage_is_aggregated():
 s=Path('app/agent_core_v2_clean/internal_knowledge.py').read_text()
 assert 'aggregate_usage' in s and 'aggregate_latency_ms' in s
def test_phase_gate_detects_unknown_telemetry():
 from app.agent_core_v2_clean.phase_gate import assess_internal_phase
 r=assess_internal_phase({'turns':[],'telemetry':{'by_purpose':{'unknown':{'calls':1}}}})
 assert not r['approved'] and r['findings'][0]['code']=='telemetry_unknown_purpose'
def test_phase_gate_approves_valid_cache_turn():
 from app.agent_core_v2_clean.phase_gate import assess_internal_phase
 s={'turns':[{'answer':{'mode':'controlled_internal_knowledge','finish_reason':'stop'},'internal_knowledge':{'cache_hit':True,'validation':{'separation_valid':True,'internal_citations':[]}},'turn_metrics':{'calls':0}}],'telemetry':{'by_purpose':{}}}
 assert assess_internal_phase(s)['approved']
def test_syntax():
 for f in ('app/agent_core_v2_clean/internal_knowledge.py','app/agent_core_v2_clean/phase_gate.py'):ast.parse(Path(f).read_text())
def test_no_product_specific_rules():
 s=Path('app/agent_core_v2_clean/phase_gate.py').read_text().casefold()
 for x in ('papercut','active directory','pin','template_fac'):assert x not in s
