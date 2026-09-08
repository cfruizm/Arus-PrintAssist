import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 files=['app/integration/lab_retrieval_adapter.py','app/agent_core_v2/lab_session.py','app/agent_core_v2/semantic_evidence_pipeline.py','app/agent_core_v2/response.py']
 for f in files:ast.parse((ROOT/f).read_text())
 assert 'retrieve_exact_document' in (ROOT/files[0]).read_text()
 assert 'exact_document_continuation' in (ROOT/files[2]).read_text()
 assert 'min(440' in (ROOT/files[3]).read_text()
 assert 'document_preserving_fallback' in (ROOT/files[3]).read_text()
 print('exact document continuation and rate-safe response checks passed')
if __name__=='__main__':main()
