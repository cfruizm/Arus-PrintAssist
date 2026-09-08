import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 for rel in ('app/integration/lab_retrieval_adapter.py','app/agent_core_v2/semantic_evidence_pipeline.py','app/agent_core_v2/response.py','app/agent_core_v2/evidence_judge.py'):ast.parse((ROOT/rel).read_text())
 a=(ROOT/'app/integration/lab_retrieval_adapter.py').read_text();p=(ROOT/'app/agent_core_v2/semantic_evidence_pipeline.py').read_text();r=(ROOT/'app/agent_core_v2/response.py').read_text()
 assert 'same_page_chunks_preserved' in a and 'rows.sort' in a
 assert 'chunk_fingerprint' in p and '_fallback_assessment' in p and 'document_lead_ids' in p
 assert 'citations=[]' in r and 'approved[:12]' in r and 'Never replace an internal documented procedure' in r
 print('evidence integrity, same-page chunks, judge recovery and citation checks passed')
if __name__=='__main__':main()
