from .semantic_contract import build_response_contract,validate_response_contract

def reconcile(result,memory):
 u=type("U",(),result.get("understanding") or {})();contract=build_response_contract(memory,u,result.get("retrieval") or {});validation=validate_response_contract((result.get("answer") or {}).get("text"),contract)
 result["response_contract"]=contract;result["response_reconciliation"]=validation
 if (result.get("answer") or {}).get("mode")=="retrieval_diagnostic":
  result["functional_events"]=[{"type":"diagnostic_text_suppressed","severity":"high"}]
  result["answer"]={"text":"Encontré documentación relacionada, pero no pude completar una respuesta final dentro del presupuesto de esta sesión.","mode":"controlled_budget_fallback","knowledge_used":False,"documented_evidence_used":False,"internal_knowledge_used":False,"knowledge_mode":"none"}
 return result
