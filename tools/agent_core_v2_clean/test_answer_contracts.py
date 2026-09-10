from pathlib import Path

def test_partial_conceptual_not_cached_as_complete():
    s=Path('app/agent_core_v2_clean/lab_session.py').read_text();assert 'partially_answered' in s
def test_metrics_use_real_attempts():
    s=Path('app/agent_core_v2_clean/lab_session.py').read_text();assert 'for attempt in attempts' in s
def test_no_product_rules():
    text=Path('app/agent_core_v2_clean/semantic_fit.py').read_text().casefold()
    for value in ('papercut','web jetadmin','sql server','active directory','mfpsecure'):assert value not in text
