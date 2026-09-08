from app.agent_core_v2.answer_policy import answer_mode,knowledge_flags,sanitize_visible_answer
from app.agent_core_v2.intent_reconciler import suspicious

def main():
 assert suspicious({"conversation_act":"clarification","intent":"procedural","requires_documents":True})
 assert suspicious({"conversation_act":"technical_request","intent":"requirements","reasoning_summary":"clear purpose question"})
 assert answer_mode([],False)=="guarded_internal_knowledge"
 assert knowledge_flags("guarded_internal_knowledge",True)["internal_knowledge_warning_shown"]
 assert "aprobada" not in sanitize_visible_answer("La documentación aprobada no contiene información")
 print("integrated hybrid coverage invariants passed")
if __name__=="__main__":main()
