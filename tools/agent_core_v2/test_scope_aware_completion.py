import ast
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def main():
 for f in ('app/agent_core_v2/lab_session.py','app/agent_core_v2/semantic_evidence_pipeline.py','app/agent_core_v2/response.py','app/agent_core_v2/evidence_judge.py','app/integration/lab_retrieval_adapter.py'):ast.parse((R/f).read_text())
 lab=(R/'app/agent_core_v2/lab_session.py').read_text();resp=(R/'app/agent_core_v2/response.py').read_text();pipe=(R/'app/agent_core_v2/semantic_evidence_pipeline.py').read_text()
 assert 'LLM_ANSWER_MAX_TOKENS",700' in lab and 'retrieve_exact_document' in lab
 assert 'request_scope' in resp and 'target_words' in resp and 'selected_evidence_ids' in resp
 assert 'broad_request":not specific' in pipe and 'deterministic_recoveries' in pipe
 print('scope, completion budget, evidence selection and knowledge telemetry checks passed')
if __name__=='__main__':main()
