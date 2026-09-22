from __future__ import annotations
from types import SimpleNamespace
from app.agent_core_v2_clean.models import ConversationMemory, TurnUnderstanding
from app.agent_core_v2_clean.reconciler import TurnReconciler
from app.agent_core_v2_clean.memory import apply_understanding, failed_actions
from app.agent_core_v2_clean.agent import CleanConversationalAgent
from app.agent_core_v2_clean.budget import BudgetPolicy
import app.agent_core_v2_clean.agent as agent_mod


def _r(text,purpose):
    return SimpleNamespace(ok=True,text=text,provider="fake",model="fake",usage={"prompt_tokens":5,"completion_tokens":10,"total_tokens":15},finish_reason="stop",purpose=purpose,error_code=None,error_message=None,to_dict=lambda:{"ok":True,"text":text,"provider":"fake","model":"fake","usage":{"prompt_tokens":5,"completion_tokens":10,"total_tokens":15},"finish_reason":"stop","purpose":purpose})

class FakeGateway:
    def complete(self,request):
        if request.purpose.endswith("understanding"):
            return _r('{"user_act":"new_request","intent":"troubleshooting","topic_relation":"new_topic","domain_relevance":"in_scope","current_goal":"resolver que no imprime","goal_complete":false,"goal_updates":{"product":"PaperCut MF","symptom":"Los trabajos no imprimen"},"case_updates":[],"needs_clarification":false,"clarification_target":null,"should_retrieve":true,"confidence":0.95,"reasoning_summary":"falla clara"}',request.purpose)
        return _r("La validación está respaldada por [R1].",request.purpose)

def _fake_search(self,query,current_only=None):
    return {"enabled":True,"ok":True,"evidence":[{"title":"Troubleshooting PaperCut MF","url":"https://internal/doc","text":"Validación inicial para trabajos que no imprimen.","metadata":{"product":"PaperCut MF"}}],"count":1,"llm_called":False,"production_state_changed":False}

def check_active_case_priority():
    m=ConversationMemory();m.active_topic="PaperCut";m.pending_goal.summary="resolver falla";m.pending_goal.intent="troubleshooting";m.support_case.status="diagnosing"
    u=TurnUnderstanding("follow_up","troubleshooting","same_topic","in_scope","siguiente paso",False,{},[],True,"modelo exacto",True,.9,"",False)
    u,_=TurnReconciler().reconcile(u,m,"¿qué hago ahora?")
    assert not u.needs_clarification and TurnReconciler().decision(u,m)["action"]=="retrieve"

def check_new_topic_isolation():
    from app.agent_core_v2_clean.models import SupportCase
    m=ConversationMemory(active_topic="PaperCut",support_case=SupportCase(status="diagnosing",symptoms=["error"]))
    u=TurnUnderstanding("new_request","conceptual","new_topic","in_scope","explicar otra herramienta",False,{},[],False,None,True,.9,"",False)
    apply_understanding(m,u)
    assert m.active_topic=="explicar otra herramienta" and m.support_case.status=="idle" and m.case_history

def check_failed_action_memory():
    m=ConversationMemory();m.support_case.attempts=[{"action":"Reiniciar servicio de impresión","result":"failed"}]
    assert failed_actions(m)==["Reiniciar servicio de impresión"]

def check_agent_flow():
    original=agent_mod.ReadOnlyRetrieval.search
    agent_mod.ReadOnlyRetrieval.search=_fake_search
    try:
        a=CleanConversationalAgent(FakeGateway(),BudgetPolicy.for_mode("normal"));m=ConversationMemory();r=a.process("PaperCut MF no imprime",m)
        assert r["decision"]["action"]=="retrieve"
        assert r["retrieval"]["selected"][0]["id"]=="R1"
        assert "[R1]" in r["answer"]["text"]
        assert m.support_case.status=="diagnosing"
    finally:
        agent_mod.ReadOnlyRetrieval.search=original

def main():
    checks=[check_active_case_priority,check_new_topic_isolation,check_failed_action_memory,check_agent_flow]
    for fn in checks: fn(); print(f"PASS {fn.__name__}")
    print(f"BEHAVIOR CHECK: PASS ({len(checks)} checks, 0 production changes)")

if __name__=="__main__": main()
