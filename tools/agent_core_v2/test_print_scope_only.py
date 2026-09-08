import ast
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def main():
 for n in ['models.py','interpreter.py','decision.py','response.py']:ast.parse((R/'app/agent_core_v2'/n).read_text())
 text=''.join((R/'app/agent_core_v2'/n).read_text() for n in ['models.py','interpreter.py','decision.py','response.py'])
 for x in ['domain_relevance','semantic_print_scope_boundary','decline_out_of_scope']:assert x in text
 assert 'Shakira' not in text
 # Ensure this package does not contain or alter escalation state/workflow implementation.
 assert not (R/'app/agent_core_v2/transitions.py').exists()
 assert not (R/'app/agent_core_v2/lab_session.py').exists()
 print('printing scope gate passed; existing escalation implementation untouched')
if __name__=='__main__':main()
