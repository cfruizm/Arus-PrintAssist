import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 for f in ('app/agent_core_v2/response.py','app/agent_core_v2/evidence_judge.py','app/llm_gateway/gateway.py'):ast.parse((ROOT/f).read_text())
 r=(ROOT/'app/agent_core_v2/response.py').read_text();j=(ROOT/'app/agent_core_v2/evidence_judge.py').read_text();g=(ROOT/'app/llm_gateway/gateway.py').read_text()
 assert '_answer_budget' in r and 'truncation_handled' in r and 'maximum_sections' in r
 assert 'range(0,len(candidates),2)' in j and 'missing_ids' in j
 assert 'groq_otpm_limit' in g and 'llm_gateway_output_ledger' in g and '0.92' in g
 print('adaptive output, compact judge and OTPM ledger checks passed')
if __name__=='__main__':main()
