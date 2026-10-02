from __future__ import annotations
import json
from app.llm_gateway.config import load_gateway_config
from .models import ConversationMemory
from .understanding import ConversationUnderstanding
from .unified_evidence_authority import apply_unified_evidence_verdict
from .response_planner import build_response_plan
from .telemetry import empty,add_result
from .internal_knowledge import validate_internal

class Result:
    def __init__(self,text,finish_reason="stop",purpose="agent_core_v2_clean_understanding"):
        self.ok=True;self.text=text;self.finish_reason=finish_reason;self.error_code=None
        self.provider="fixture";self.model="fixture";self.usage={"prompt_tokens":10,"completion_tokens":10,"total_tokens":20};self.latency_ms=1;self.purpose=purpose
    def to_dict(self):return {"ok":True,"text":self.text,"finish_reason":self.finish_reason,"usage":self.usage,"latency_ms":1,"purpose":self.purpose}
class Gateway:
    def __init__(self,items):self.items=list(items);self.calls=0
    def complete(self,request):out=self.items[self.calls];self.calls+=1;return out

def complete(workflow="start_escalation"):
    return json.dumps({"user_act":"follow_up","intent":"troubleshooting","topic_relation":"same_topic","domain_relevance":"in_scope","current_goal":"Transferir el caso actual","goal_complete":False,"goal_updates":{},"case_updates":[],"needs_clarification":False,"clarification_target":None,"should_retrieve":False,"confidence":0.96,"reasoning_summary":"Operational workflow requested","canonical_subject":"Print platform","subject_origin":"conversation_memory","reference_relation":"current_subject","requested_workflow":workflow})

def run():
    cfg=load_gateway_config({"LLM_ORCHESTRATOR_MAX_TOKENS":220})
    ok_gateway=Gateway([Result('{"user_act":"follow_up"}',"length"),Result(complete(),"stop")])
    engine=ConversationUnderstanding(ok_gateway,350);u=engine.interpret("fixture",ConversationMemory(active_subject="Print platform"))
    bad_gateway=Gateway([Result('{"user_act":"follow_up"}',"length"),Result('{"user_act":"follow_up"}',"length")])
    bad=ConversationUnderstanding(bad_gateway,350);degraded=bad.interpret("fixture",ConversationMemory(active_subject="Print platform"))

    retrieval={"enabled":True,"ok":True,"query":{"fields":{"current_message":"release jobs incident","goal":"diagnose release failure"}},"generation_evidence":[{"id":"raw1","title":"Release workflow reference","text":"The platform can prevent job release when a destination device reports an error.","source":"doc://release","semantic_fit":{"score":0.6}}]}
    authorized=apply_unified_evidence_verdict(retrieval,"Users cannot release jobs",{"intent":"troubleshooting","current_goal":"Diagnose release failure","canonical_subject":"Print platform"})
    plan=build_response_plan("Users cannot release jobs",{"intent":"troubleshooting","current_goal":"Diagnose release failure","goal_updates":{}},authorized,{"status":(authorized.get("evidence_verdict") or {}).get("status")})

    telemetry=empty();compound={"initial":Result("{}","length").to_dict(),"repair":Result(complete(),"stop").to_dict(),"repair_attempted":True}
    add_result(telemetry,compound,True)
    pure_ok,_=validate_internal("### Orientación sugerida\n\nValida el estado actual.\n\n**Siguiente paso:** registra el resultado.","stop",[])
    hybrid_ok,_=validate_internal("### Según la documentación\n\nLa liberación puede bloquearse ante un error [R1].\n\n### Validaciones adicionales\n\nComprueba el estado del destino.","stop",["R1"])
    checks={
      "dedicated_understanding_cap_default_360":cfg["understanding_max_tokens"]==360,
      "orchestrator_cap_remains_220":cfg["orchestrator_max_tokens"]==220,
      "complete_repair_recovers_workflow":engine.contract_valid and u.requested_workflow=="start_escalation",
      "truncated_repair_rejected":not bad.contract_valid and degraded.degraded and bad.normalization.get("repair_truncated") is True,
      "semantic_troubleshooting_evidence_partial":(authorized.get("evidence_verdict") or {}).get("status")=="partial",
      "partial_evidence_preserved":bool((authorized.get("evidence_verdict") or {}).get("selected_evidence")),
      "partial_routes_hybrid":plan.response_plan["mode"]=="hybrid",
      "compound_trace_counts_two_calls":telemetry["calls"]==2,
      "truncation_not_provider_failure":telemetry["provider_failed_calls"]==0,
      "compact_formats_valid":pure_ok and hybrid_ok,
    }
    failed=[k for k,v in checks.items() if not v]
    return {"phase":"4B.3.2","status":"passed" if not failed else "failed","passed":len(checks)-len(failed),"failed":len(failed),"failed_checks":failed,"checks":checks}
if __name__=="__main__":
    r=run();print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r["status"]=="passed" else 1)
