from .semantic_contract import build_response_contract,validate_response_contract

def reconcile(result,memory):
 contract=build_response_contract(memory,type("U",(),result.get("understanding") or {})(),result.get("retrieval") or {})
 validation=validate_response_contract((result.get("answer") or {}).get("text"),contract)
 result["response_contract"]=contract;result["response_reconciliation"]=validation
 return result
