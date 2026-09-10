from pathlib import Path
import ast

def test_lab_session_syntax():ast.parse(Path('app/agent_core_v2_clean/lab_session.py').read_text())
def test_answer_context_persisted():
    s=Path('app/agent_core_v2_clean/lab_session.py').read_text();assert 'answer_context' in s and 'capture_answer_context' in s
def test_followup_uses_answer_context():
    s=Path('app/agent_core_v2_clean/lab_session.py').read_text();assert 'apply_semantic_fit(raw, store.get("answer_context"))' in s
def test_no_pages_added():assert not Path('pages').exists()
