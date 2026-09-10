from app.agent_core_v2_clean.answer_context_policy import enrich_internal_payload
from pathlib import Path
import ast

def test_followup_payload_uses_previous_answer():
 p=enrich_internal_payload({'question':'follow'}, {'goal':'g','main_text_excerpt':'prior','source_titles':['d']}, {'user_act':'follow_up'})
 assert p['previous_answer_context']['main_text_excerpt']=='prior'
def test_internal_composer_integrated():
 s=Path('app/agent_core_v2_clean/internal_knowledge.py').read_text();assert 'enrich_internal_payload' in s and 'answer_context_used' in s
def test_syntax():
 for f in ('semantic_fit.py','answer_context_policy.py','internal_knowledge.py','lab_session.py'):ast.parse(Path('app/agent_core_v2_clean',f).read_text())
def test_no_product_rules():
 text=''.join(Path('app/agent_core_v2_clean',f).read_text().casefold() for f in ('semantic_fit.py','answer_context_policy.py','internal_knowledge.py'))
 for x in ('papercut','mfpsecure','web jetadmin','sql server'):assert x not in text
