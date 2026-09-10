from app.agent_core_v2_clean.semantic_fit import evaluate_item, apply_semantic_fit

def test_unconfirmed_document_scope_is_penalized():
    item={"id":"R1","title":"Advanced clustered database migration","text":"Configure service account and integrated database security."}
    fit=evaluate_item(item,"Configure user authentication",{"goal":"Configure user authentication"},{})
    assert fit["assumption_penalty"]>0

def test_followup_boosts_previous_source_without_locking():
    item={"id":"R1","title":"Access validation guide","source":"doc-a","text":"Verify compatibility before enabling access."}
    fit=evaluate_item(item,"What should be verified first?",{"goal":"Configure secure access","user_act":"follow_up"},{"source_identities":["doc-a"]})
    assert fit["continuity_boost"]>0

def test_retrieval_is_ranked_by_fit():
    r={"query":{"text":"verify secure access","fields":{"goal":"secure access"}},"evidence":[{"id":"R1","title":"Unrelated billing export","text":"invoice totals"},{"id":"R2","title":"Secure access checks","text":"verify supported authentication and compatibility"}],"selection":{"quality":0.5}}
    out=apply_semantic_fit(r,{})
    assert out["evidence"][0]["id"]=="R2"
