from __future__ import annotations
import json
from .contracts import UNDERSTANDING_SCHEMA
from .models import ConversationMemory, TurnUnderstanding
from .memory import compact_context, normalize_goal_updates

SYSTEM = """
Eres el intérprete semántico de Arus PrintAssist. NO respondes al usuario.
Analiza solo el turno actual usando el contexto entregado.
Debes reconstruir: acto del usuario, intención, relación con el tema, objetivo actual y hechos nuevos.
No inventes productos ni hechos. No preguntes por información que ya esté confirmada.
Un follow-up dentro de un caso activo mantiene el contexto. Un cambio de producto o necesidad independiente crea un nuevo tema sin borrar el historial anterior.
Una pregunta conceptual clara NO necesita aclaración. En troubleshooting, registra síntomas, acciones intentadas y resultado del intento como case_updates.
Pide aclaración solo cuando un dato sea realmente indispensable para escoger entre respuestas/procedimientos diferentes.
""".strip()
REQUIRED=set(UNDERSTANDING_SCHEMA["required"])

class ConversationUnderstanding:
    def __init__(self,gateway,max_tokens=320):
        self.gateway=gateway;self.max_tokens=max(220,min(420,int(max_tokens)));self.last_provider_result={};self.contract_valid=False;self.validation_error=None;self.normalization={}

    def _degraded(self,memory,reason):
        return TurnUnderstanding("follow_up",memory.pending_goal.intent or "unknown","same_topic","uncertain",memory.pending_goal.summary or memory.active_topic or "",False,{},[],False,None,False,0.0,reason,True)

    def _parse(self,text):
        raw=json.loads(str(text or "").strip().strip("`").replace("```json","",1).rstrip("`").strip())
        if not isinstance(raw,dict):raise ValueError("decision_not_object")
        missing=REQUIRED-set(raw)
        if missing:raise ValueError("missing_fields:"+",".join(sorted(missing)))
        raw["goal_updates"],removed=normalize_goal_updates(raw.get("goal_updates"));self.normalization={"removed_goal_update_keys":removed}
        raw["confidence"]=max(0.0,min(1.0,float(raw.get("confidence",0.0))))
        raw["reasoning_summary"]=str(raw.get("reasoning_summary") or "")[:180]
        raw["current_goal"]=str(raw.get("current_goal") or "").strip()
        raw["clarification_target"]=(str(raw.get("clarification_target")).strip() if raw.get("clarification_target") else None)
        return TurnUnderstanding(**raw)

    def interpret(self,message,memory):
        from app.llm_gateway.models import LLMRequest
        request=LLMRequest([{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps({"message":str(message),"context":compact_context(memory)},ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_clean_understanding",self.max_tokens,0.0,UNDERSTANDING_SCHEMA)
        r=self.gateway.complete(request);self.last_provider_result=r.to_dict();self.contract_valid=False;self.validation_error=None
        if not r.ok:self.validation_error="provider_error:"+str(r.error_code or "unknown");return self._degraded(memory,self.validation_error)
        try:
            u=self._parse(r.text)
            corrections=[]
            if not u.current_goal and memory.pending_goal.summary:u.current_goal=memory.pending_goal.summary;corrections.append("empty_goal_reused")
            if u.user_act=="answer_to_question" and not memory.last_assistant_question:u.user_act="follow_up" if memory.pending_goal.summary else "new_request";corrections.append("orphan_answer_normalized")
            if u.user_act in {"follow_up","request_elaboration","reported_failure","attempt_result"} and memory.pending_goal.summary and u.topic_relation=="new_topic":u.topic_relation="same_topic";corrections.append("active_goal_continuity_preserved")
            if u.intent=="conceptual" and u.domain_relevance=="in_scope":u.needs_clarification=False;u.clarification_target=None;u.should_retrieve=True
            if u.needs_clarification and not u.clarification_target:u.needs_clarification=False;corrections.append("empty_clarification_suppressed")
            if u.intent=="troubleshooting":
                existing={str(x.get("type")) for x in u.case_updates}
                for key in ("symptom","observation","affected_scope","attempted_action","attempt_result","error_message"):
                    value=str((u.goal_updates or {}).get(key) or "").strip()
                    if value and key not in existing:u.case_updates.append({"type":key,"value":value});corrections.append("goal_fact_promoted:"+key)
            if memory.support_case.status=="diagnosing" and u.user_act in {"follow_up","request_elaboration","answer_to_question","attempt_result"}:
                u.should_retrieve=True
                if u.intent=="unknown":u.intent=memory.pending_goal.intent or "troubleshooting"
                corrections.append("active_case_retrieval_enforced")
            self.normalization.setdefault("structural_corrections",[]).extend(corrections)
            self.contract_valid=True;return u
        except Exception as exc:
            self.validation_error=str(exc);return self._degraded(memory,"invalid_understanding:"+self.validation_error)
