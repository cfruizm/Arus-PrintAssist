import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 for rel in ('app/agent_core_v2/semantic_evidence_pipeline.py','app/agent_core_v2/response.py','app/agent_core_v2/evidence_judge.py'):ast.parse((ROOT/rel).read_text())
 pipe=(ROOT/'app/agent_core_v2/semantic_evidence_pipeline.py').read_text();resp=(ROOT/'app/agent_core_v2/response.py').read_text()
 assert '_is_document_lead' in pipe and 'applicability describes the current excerpt'.casefold() in pipe.casefold()
 assert 'exact_document_continuation' in pipe and 'document_lead_ids' in pipe
 assert 'approved[:8]' in resp and '"excerpt"' in resp
 assert 'Never replace a documented internal procedure' in resp
 print('document authority, exact continuation and full excerpt composition checks passed')
if __name__=='__main__':main()
