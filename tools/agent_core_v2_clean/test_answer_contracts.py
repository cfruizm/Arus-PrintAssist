from pathlib import Path
import ast

def test_syntax():
 for f in ('semantic_fit.py','answer_context_policy.py'):ast.parse(Path('app/agent_core_v2_clean',f).read_text())
def test_no_product_rules():
 s=Path('app/agent_core_v2_clean/semantic_fit.py').read_text().casefold()
 for x in ('papercut','mfpsecure','web jetadmin','sql server','active directory'):assert x not in s
def test_followup_policy_is_generic():
 s=Path('app/agent_core_v2_clean/answer_context_policy.py').read_text();assert 'generic checklist' in s and 'unconfirmed scenario' in s
