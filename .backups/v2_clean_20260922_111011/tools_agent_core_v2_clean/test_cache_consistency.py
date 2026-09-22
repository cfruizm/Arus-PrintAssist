from types import SimpleNamespace
from app.agent_core_v2_clean.memory import normalize_goal_updates
def test_structural_goal_keys_are_removed():
 clean,removed=normalize_goal_updates({'intent':'conceptual','status':'active','subject':'tool'})
 assert clean=={'subject':'tool'} and removed==['intent','status']
def test_artifact_does_not_require_historical_turn_copy():
 keys={'understanding','understanding_contract','goal_update_normalization','decision','answer','retrieval'}
 assert 'state_before' not in keys and 'provider_trace' not in keys
