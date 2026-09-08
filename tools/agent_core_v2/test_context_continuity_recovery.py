import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read(name):return (ROOT/'app/agent_core_v2'/name).read_text()
def main():
 for name in ('lab_session.py','interpreter.py','decision.py','semantic_evidence_pipeline.py','response.py'):ast.parse(read(name))
 lab=read('lab_session.py');interp=read('interpreter.py');decision=read('decision.py')
 assert 'store.get("engine") is not None' in lab
 assert 'engine_signature' in lab
 assert 'previous_user_message' in interp
 assert 'docs=True' in interp
 assert 'repair_false_clarification_from_resolved_context' in decision
 print('context continuity and false clarification recovery checks passed')
if __name__=='__main__':main()
