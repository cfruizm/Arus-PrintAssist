from app.agent_core_v2_clean.session_lifecycle import reset_new_conversation,budget_snapshot
from app.agent_core_v2_clean.recovery_policy import should_recover_with_controlled_knowledge

def test_new_conversation_resets_budget_and_messages():
 s={'messages':[1],'turns':[2],'telemetry':{'total_tokens':13900},'unrelated':'keep','agent_core_v2_clean_old':object()};r=reset_new_conversation(s);assert s['messages']==[] and s['turns']==[] and s['telemetry']['total_tokens']==0 and s['unrelated']=='keep' and r.session_id
def test_budget_snapshot_uses_new_runtime():
 s={};r=reset_new_conversation(s);snap=budget_snapshot(r,14000,1200);assert snap['available_after_reserve']==12800
def test_guard_can_recover():assert should_recover_with_controlled_knowledge({'mode':'procedural_citation_guard'},{'status':'partial'})
def test_normal_answer_does_not_recover():assert not should_recover_with_controlled_knowledge({'mode':'procedural_documented_answer'},{'status':'sufficient'})
def test_internal_prompt_is_context_conditional():
 from app.agent_core_v2_clean.internal_knowledge_policy import CONTEXT_APPLICABILITY_POLICY
 assert 'solo si la pregunta trata sobre identidad' in CONTEXT_APPLICABILITY_POLICY and 'Para firmware, red, colas' in CONTEXT_APPLICABILITY_POLICY
def test_no_pages_directory():
 from pathlib import Path
 assert not Path('pages').exists()
