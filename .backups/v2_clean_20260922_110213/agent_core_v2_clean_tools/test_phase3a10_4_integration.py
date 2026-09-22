from pathlib import Path

def test_lab_session_preempts_conceptual_documented_composer():
    text = Path('app/agent_core_v2_clean/lab_session.py').read_text(encoding='utf-8')
    assert 'from .conceptual_route import must_preempt_documented_answer' in text
    start = text.index('def _answers(')
    end = text.index('def _trace_list(', start)
    block = text[start:end]
    assert block.index('must_preempt_documented_answer') < block.index('_conceptual(result')
    assert 'conceptual_preempted_by_controlled_synthesis' in block
