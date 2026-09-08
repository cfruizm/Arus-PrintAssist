import ast
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def main():
 for f in ('app/agent_core_v2/lab_session.py','app/agent_core_v2/response.py'):ast.parse((R/f).read_text())
 lab=(R/'app/agent_core_v2/lab_session.py').read_text();resp=(R/'app/agent_core_v2/response.py').read_text()
 assert 'LLM_ANSWER_MAX_TOKENS",900' in lab and 'retrieve_exact_document' in lab
 assert 'canonical_escalation' in resp and 'AWS' not in resp and 'Never mention token limits' in resp
 assert 'answer_closed_naturally' in resp and 'Do not expose personal email addresses' in resp
 print('natural response, safe closure, focused scope and canonical escalation checks passed')
if __name__=='__main__':main()
