from app.agent_core_v2_clean.telemetry import normalize,empty
def test_legacy_failed_calls_migrates():
 x=normalize({'calls':2,'failed_calls':1,'total_tokens':524,'by_purpose':{'u':{'calls':2,'failed_calls':1,'total_tokens':524}}})
 assert x['provider_failed_calls']==1 and x['functional_failed_calls']==1
 assert x['by_purpose']['u']['provider_failed_calls']==1
def test_new_schema_remains_stable():
 x=normalize(empty());assert x['schema_version']==2 and x['functional_failed_calls']==0
def test_missing_keys_are_safe():
 x=normalize({'total_tokens':0});assert x['calls']==0 and x['contract_failed_calls']==0
