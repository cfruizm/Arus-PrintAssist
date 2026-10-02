from __future__ import annotations
import json
from .models import ConversationMemory
from .understanding import ConversationUnderstanding
from .topic_boundary import infer_topic_boundary
from .response_planner import build_response_plan
from .internal_knowledge import validate_internal

class Result:
    def __init__(self,text,finish_reason="stop"):
        self.ok=True;self.text=text;self.finish_reason=finish_reason
        self.error_code=None;self.provider="fixture";self.model="fixture";self.usage={};self.latency_ms=0
    def to_dict(self):
        return {"ok":self.ok,"text":self.text,"finish_reason":self.finish_reason,"usage":{}}

class Gateway:
    def __init__(self,results):self.results=list(results);self.calls=0
    def complete(self,request):
        out=self.results[self.calls];self.calls+=1;return out

def run():
    partial=json.dumps({"user_act":"follow_up","intent":"troubleshooting","topic_relation":"same_topic","domain_relevance":"in_scope","current_goal":"Escalar el caso actual"},ensure_ascii=False)
    repaired=json.dumps({"user_act":"follow_up","intent":"troubleshooting","topic_relation":"same_topic","domain_relevance":"in_scope","current_goal":"Escalar el caso actual","goal_complete":False,"goal_updates":{},"case_updates":[],"needs_clarification":False,"clarification_target":None,"should_retrieve":False,"confidence":0.96,"reasoning_summary":"Operational workflow requested","canonical_subject":"PaperCut MF","subject_origin":"conversation_memory","reference_relation":"current_subject","requested_workflow":"start_escalation"},ensure_ascii=False)
    gateway=Gateway([Result(partial,"length"),Result(repaired,"stop")])
    understanding=ConversationUnderstanding(gateway,350)
    parsed=understanding.interpret("fixture",ConversationMemory(active_subject="PaperCut MF"))

    previous={"pending_goal":{"summary":"Resolver trabajos retenidos en la cola","known_details":{"subject":"impresora","operation":"diagnosticar cola"}}}
    turn={"user_act":"answer_to_question","intent":"troubleshooting","topic_relation":"same_topic","current_goal":"Registrar validaciones y continuar el diagnóstico","goal_updates":{"operation":"continuar diagnóstico"},"case_updates":[{"type":"attempted_action","value":"validación realizada","result":"sin cambio"}]}
    boundary=infer_topic_boundary(previous,turn)

    evidence={"id":"R1","text":"Documented device error behavior","source":"PaperCut MF guide","page":1}
    retrieval={"evidence_verdict":{"status":"partial","generation_mode":"documented_plus_internal","accepted":False,"selected_evidence":[evidence]}}
    plan=build_response_plan("fixture",{"intent":"troubleshooting","current_goal":"Diagnose","goal_updates":{}},retrieval,{"status":"partial"})

    pure_ok,pure_diag=validate_internal("### Orientación sugerida\n\nRealiza una validación segura.\n\n**Siguiente paso:** revisa el resultado.","stop",[])
    hybrid_ok,hybrid_diag=validate_internal("### Según la documentación\n\nEl dispositivo puede bloquear la liberación [R1].\n\n### Validaciones adicionales\n\nComprueba el estado actual.","stop",["R1"])

    checks={
        "truncated_understanding_repaired":gateway.calls==2 and understanding.contract_valid,
        "workflow_recovered_on_first_turn":parsed.requested_workflow=="start_escalation",
        "workflow_disables_retrieval":parsed.should_retrieve is False,
        "diagnostic_case_update_preserves_topic":boundary.relation=="same_topic_refinement",
        "diagnostic_evidence_role_primary":boundary.previous_evidence_role=="primary",
        "partial_evidence_routes_hybrid":plan.response_plan["mode"]=="hybrid",
        "partial_evidence_preserved":bool(plan.evidence_plan["selected_evidence"]),
        "compact_internal_format_valid":pure_ok and pure_diag.get("compact_format"),
        "compact_hybrid_format_valid":hybrid_ok and hybrid_diag.get("compact_format"),
    }
    failed=[name for name,ok in checks.items() if not ok]
    return {"phase":"4B.3.1","status":"passed" if not failed else "failed","passed":len(checks)-len(failed),"failed":len(failed),"failed_checks":failed,"checks":checks}

if __name__=="__main__":
    result=run();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result["status"]=="passed" else 1)
