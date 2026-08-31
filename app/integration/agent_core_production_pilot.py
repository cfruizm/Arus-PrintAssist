from __future__ import annotations
import re
import time
from app.agent_core.conversation_act_runtime import compact_case_state
from app.agent_core.hybrid_response_lab import run_hybrid_response_lab, select_evidence
from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
from app.integration.semantic_real_chat_shadow import observe_semantic_real_chat_turn
from app.integration.session_adapter_v1 import get_or_create_router_shadow_state
from app.llm_gateway.config import load_gateway_config
from app.llm_gateway.gateway import LLMGateway

GLOBAL_CANCEL_COMMANDS={"salir","cancelar","cancela","abortar","olvidar el caso","cancelar escalamiento","detener escalamiento"}
INDEPENDENT_ACTS={"ask_concept","request_procedure","request_support","request_next_step","ask_requirements","ask_architecture","provide_case_detail"}
REQUEST_INTENTS={"conceptual","procedural","requirements","architecture","warranty","troubleshooting"}
PROCEDURAL_MARKERS=("cómo puedo","como puedo","necesito crear","necesito configurar","quiero crear","quiero configurar","asignar","habilitar","instalar","configurar","crear un","pasos para")
CONCEPTUAL_MARKERS=("qué es","que es","para qué sirve","para que sirve","qué hace","que hace","explica")
REQUIREMENT_MARKERS=("requisitos","prerrequisitos","compatible","compatibilidad","sistema operativo","hardware")


def _norm(value):return " ".join(str(value or "").casefold().strip(" ¿?¡!.,:;").split())

def _clear_router_state(streamlit_state):
    removed=[]
    for key in list(streamlit_state.keys()):
        lowered=str(key).casefold()
        if any(token in lowered for token in ("router_shadow","agent_core_router","semantic_case_state","technical_case")):
            try:del streamlit_state[key];removed.append(key)
            except Exception:pass
    return removed

def reset_all_conversation_states(chat_session_state,streamlit_state):
    chat_session_state.mode="normal";chat_session_state.pending_incident_field=None;chat_session_state.escalation_workflow_state="normal";chat_session_state.escalation_summary_ready=False;chat_session_state.escalation_persisted=False
    incident=getattr(chat_session_state,"incident_state",None)
    if incident is not None:
        for field,value in {"software_involved":None,"software_version":None,"actions_attempted":[],"error_description":None,"printer_data":None,"contract_client_location":None,"evidence":None,"impact_type":None,"escalation_requested":False}.items():
            try:setattr(incident,field,value)
            except Exception:pass
    try:chat_session_state.conversation_topic={}
    except Exception:pass
    removed=_clear_router_state(streamlit_state);streamlit_state.pop("agent_core_semantic_real_chat_last_record",None)
    return removed

def _temporary_case_state(chat_session_state,semantic_record):
    router_state=get_or_create_router_shadow_state(chat_session_state);state=compact_case_state(router_state);state={k:(list(v) if isinstance(v,list) else v) for k,v in state.items()}
    decision=semantic_record.get("normalized_decision") or semantic_record.get("model_decision") or {}
    for update in decision.get("state_updates") or []:
        typ=str(update.get("type") or "");value=str(update.get("value") or "").strip();field={"product":"products","process":"processes","symptom":"symptoms","attempted_action":"attempted_actions"}.get(typ)
        if field and value:
            state.setdefault(field,[])
            if value not in state[field]:state[field].append(value)
        elif typ=="affected_scope" and value:state["affected_scope"]=value
        elif typ=="resolution_status" and value:state["resolution_status"]=value
    return state

def _clean_user_answer(proposal):
    answer=str(proposal.get("answer_result",{}).get("text") or "").strip();sources=proposal.get("evidence_selection",{}).get("selected_sources") or [];used=set(re.findall(r"\[(S\d+)\]",answer))
    if not used:return answer
    answer=re.sub(r"\n+\*{0,2}Fuentes\*{0,2}\s*\n[\s\S]*$","",answer,flags=re.IGNORECASE).rstrip();lines=[]
    for source in sources:
        sid=str(source.get("id") or "")
        if sid not in used:continue
        title=str(source.get("title") or sid).strip();url=str(source.get("url") or "").strip();lines.append(f"- [{sid}] [{title}]({url})" if url.startswith("http") else f"- [{sid}] {title}")
    return answer+("\n\n### Fuentes\n"+"\n".join(lines) if lines else "")

def _infer_intent(user_message,model_decision,derived):
    text=_norm(user_message);intent=str(derived.get("intent") or "unknown")
    if any(marker in text for marker in PROCEDURAL_MARKERS):return "procedural"
    if any(marker in text for marker in CONCEPTUAL_MARKERS):return "conceptual"
    if any(marker in text for marker in REQUIREMENT_MARKERS):return "requirements"
    return intent if intent in REQUEST_INTENTS else "unknown"

def _request_signal(user_message,model_decision,derived,intent):
    text=_norm(user_message);retrieval=model_decision.get("retrieval_request") or {};act=str(model_decision.get("conversation_act") or "")
    explicit_retrieval=bool(retrieval.get("question") and (retrieval.get("problem_statement") or retrieval.get("products")))
    linguistic_request=("?" in str(user_message) or any(marker in text for marker in PROCEDURAL_MARKERS+CONCEPTUAL_MARKERS+REQUIREMENT_MARKERS))
    return bool(derived.get("requires_retrieval") or explicit_retrieval or act in INDEPENDENT_ACTS and linguistic_request or intent in {"conceptual","procedural","requirements","architecture","warranty"} and linguistic_request)

def _canonical_entities(model_decision,case_state):
    retrieval=model_decision.get("retrieval_request") or {};products=[];processes=[]
    for value in list(retrieval.get("products") or [])+list(case_state.get("products") or []):
        value=str(value or "").strip()
        if value and value not in products:products.append(value)
    for value in list(retrieval.get("processes") or [])+list(case_state.get("processes") or []):
        value=str(value or "").strip()
        if value and value not in processes:processes.append(value)
    return {"products":products,"processes":processes}

def _fallback_for_intent(intent,query,entities,retrieval):
    product=", ".join(entities.get("products") or []) or "el producto consultado";selected=select_evidence(query,retrieval.get("evidence") or [],2);source_lines=[]
    for index,item in enumerate(selected,1):
        title=str(item.get("title") or f"Fuente {index}");url=str(item.get("url") or "");source_lines.append(f"- [{title}]({url})" if url.startswith("http") else f"- {title}")
    sources="\n".join(source_lines)
    if intent=="procedural":
        answer=f"""### Cobertura documental
La documentación recuperada no contiene pasos suficientes y directamente aplicables para realizar este procedimiento en {product}.

### Qué falta confirmar
Antes de indicar pasos, es necesario precisar la función exacta que deseas configurar y contar con una guía administrativa específica del producto. No conviene convertir documentos de requisitos, instalación general o funciones relacionadas en un procedimiento que no está documentado.

### Siguiente acción
Consulta la guía de administración correspondiente o comparte el nombre exacto de la opción visible en la consola. Si no existe documentación aplicable, escala la solicitud como consulta de configuración, no como incidente técnico."""
    elif intent=="conceptual":
        answer=f"""### Cobertura documental
La documentación recuperada no permite definir con precisión {product} dentro de este contexto.

### Respuesta acotada
No es seguro ampliar la definición con conocimiento general que pueda confundirse con otro producto o categoría tecnológica. Para una explicación confiable se requiere una fuente específica del producto de impresión.

### Siguiente acción
Consulta la ficha funcional o guía oficial del producto. Si compartes el componente o función concreta que deseas entender, puedo buscar una explicación más precisa."""
    elif intent=="requirements":
        answer=f"""### Cobertura documental
No se recuperaron requisitos suficientemente específicos para {product}.

### Información no confirmada
No es posible confirmar versiones, sistemas operativos, hardware, red, permisos o dependencias con las fuentes actuales.

### Siguiente acción
Se requiere la guía de requisitos del producto o versión exacta antes de planear la instalación o el cambio."""
    else:
        answer=f"""### Cobertura documental
La documentación recuperada no permite indicar un procedimiento confiable para este escenario en {product}.

### Evidencia por recopilar
- Usuario, equipo, impresora o cola afectados.
- Hora aproximada y mensaje exacto.
- Acción ya realizada y resultado.

### Escalamiento recomendado
Evita modificar servicios, red o configuración sin una fuente aplicable. Si el caso persiste, escala con la evidencia recopilada."""
    if sources:answer+=f"\n\n### Fuentes revisadas\n{sources}"
    return answer

def _recognized_domain_entity(entities):return bool(entities.get("products") or entities.get("processes"))

def try_agent_core_production_pilot(user_message,chat_session_state,streamlit_state,secrets):
    started=time.perf_counter();normalized=_norm(user_message);record={"input":user_message,"status":"started","fallback_to_legacy":False,"answer_visible":False,"router_version":"unified_intent_v1"}
    try:
        if normalized in GLOBAL_CANCEL_COMMANDS:
            removed=reset_all_conversation_states(chat_session_state,streamlit_state);answer="El escalamiento y el caso técnico activo fueron cancelados. Puedes continuar con una nueva consulta de soporte.";record.update(status="served",answer_visible=True,route="global_cancel",answer=answer,cleared_router_keys=removed);return answer,record
        semantic=observe_semantic_real_chat_turn(user_message,chat_session_state,streamlit_state,secrets);record["semantic"]=semantic
        if semantic.get("status")!="ok":record.update(status="fallback",fallback_to_legacy=True,reason="semantic_unavailable");return None,record
        model_decision=semantic.get("model_decision") or {};normalized_decision=semantic.get("normalized_decision") or {};derived=semantic.get("derived_decision") or {};state=_temporary_case_state(chat_session_state,semantic);intent=_infer_intent(user_message,model_decision,derived);entities=_canonical_entities(model_decision,state);request_signal=_request_signal(user_message,model_decision,derived,intent);escalation_active=str(getattr(chat_session_state,"escalation_workflow_state","normal"))=="escalation_collecting"
        record.update(intent=intent,entities=entities,request_signal=request_signal,escalation_active=escalation_active,conversation_act=model_decision.get("conversation_act"))
        if escalation_active and not request_signal:record.update(status="fallback",fallback_to_legacy=True,reason="continue_active_escalation");return None,record
        if not request_signal:record.update(status="fallback",fallback_to_legacy=True,reason="non_request_conversation");return None,record
        retrieval_request=normalized_decision.get("retrieval_request") or model_decision.get("retrieval_request") or {};question=str(retrieval_request.get("question") or user_message).strip();problem=str(retrieval_request.get("problem_statement") or "").strip();query=question
        if problem and problem.casefold() not in query.casefold():query=f"{problem}. {query}"
        if entities["products"] and not any(p.casefold() in query.casefold() for p in entities["products"]):query=f"Producto: {', '.join(entities['products'])}. {query}"
        retrieval=retrieve_from_existing_backend(query,6);record["retrieval"]=retrieval
        if not retrieval.get("ok"):record.update(status="fallback",fallback_to_legacy=True,reason="retrieval_failed");return None,record
        gateway=LLMGateway(load_gateway_config(secrets),streamlit_state);proposal=run_hybrid_response_lab(gateway,retrieval,query,state,intent,str(secrets.get("LLM_INTERNAL_KNOWLEDGE_POLICY","hybrid_guarded")),max(250,min(500,int(secrets.get("LLM_ANSWER_MAX_TOKENS",400)))));record["proposal"]=proposal
        decision=proposal.get("evidence_decision",{});mode=str(decision.get("response_mode") or "")
        # Recognized domain entities must not be explained from unconstrained model knowledge.
        if mode=="internal_general" and _recognized_domain_entity(entities):
            answer=_fallback_for_intent(intent,query,entities,retrieval);record.update(status="served",answer_visible=True,route="grounded_limit",response_mode="grounded_limit",answer=answer);return answer,record
        if mode=="escalate" and intent in {"procedural","conceptual","requirements"}:
            answer=_fallback_for_intent(intent,query,entities,retrieval);record.update(status="served",answer_visible=True,route="intent_specific_limit",response_mode=mode,answer=answer);return answer,record
        if not proposal.get("compliance",{}).get("compliant"):record.update(status="fallback",fallback_to_legacy=True,reason="proposal_non_compliant");return None,record
        answer=_clean_user_answer(proposal)
        if not answer:record.update(status="fallback",fallback_to_legacy=True,reason="empty_answer");return None,record
        record.update(status="served",answer_visible=True,route="independent_question" if escalation_active else "agent_core",provider=proposal.get("answer_result",{}).get("provider"),model=proposal.get("answer_result",{}).get("model"),response_mode=mode,answer=answer,escalation_preserved_in_pause=escalation_active);return answer,record
    except Exception as exc:
        record.update(status="fallback",fallback_to_legacy=True,reason="pilot_exception",error=f"{type(exc).__name__}: {exc}");return None,record
    finally:
        record["latency_ms"]=round((time.perf_counter()-started)*1000,3);records=list(streamlit_state.get("agent_core_production_pilot_records",[]) or []);records.append(record);streamlit_state["agent_core_production_pilot_records"]=records[-100:];streamlit_state["agent_core_production_pilot_last_record"]=record
