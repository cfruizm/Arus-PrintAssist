from __future__ import annotations
import re
from app.agent_core.case_manager_v1 import is_case_update_candidate,infer_updates,apply_updates
from app.agent_core.entity_service import detect_entities
from app.agent_core.responses_v1 import build_response
from app.agent_core.router_models import RouteDecision,RouterShadowState
from app.agent_core.router_normalizer import extract_urls,normalize_conversation_text,strip_politeness

SOCIAL={"hola","buenas","buenos dias","buenas tardes","buenas noches","gracias","muchas gracias","adios","hasta luego","ok","listo","entendido"}
CAPABILITY=(r"\bque (?:puedes|sabes) hacer\b",r"\bque funciones tienes\b",r"\bcual es tu alcance\b")
INTAKE=(r"^(?:necesito|requiero) ayuda$",r"^(?:necesito|requiero) soporte$",r"^tengo problemas?$",r"^algo no funciona$")
ESCALATION=(r"\bquiero escalar\b",r"\bnecesito escalar\b",r"\bescalar (?:este|el) caso\b",r"\babrir (?:un )?caso\b",r"\bcrear incidente\b")
FOLLOW=(r"^(?:que|cuales) (?:requisitos|funciones|componentes|versiones|limitaciones)(?: tiene)?$",r"^(?:y )?como (?:se )?(?:instala|configura|usa|funciona|actualiza|registra)$",r"^para que sirve$",r"^(?:y )?(?:como|cuando|donde|por que)$")
PRINT_TERMS={"impresora","impresion","imprimir","imprime","multifuncional","cola","trabajo","driver","firmware","escaner","escaneo","servidor","pin","codigo","papel","toner","software","plataforma","dispositivo","red","usb","error","falla"}
ACTION_TERMS={"como","que","cual","configurar","instalar","agregar","asignar","revisar","hacer"}

def matches(patterns,text): return any(re.search(p,text) for p in patterns)
def topic_count(state): return len(state.topic.products)+len(state.topic.processes)
def looks_technical(text):
    tokens=set(text.split()); return bool(tokens&PRINT_TERMS) and (bool(tokens&ACTION_TERMS) or len(tokens&PRINT_TERMS)>=2)

def route_message(message: str,state: RouterShadowState) -> RouteDecision:
    raw=str(message or "").strip(); urls=extract_urls(raw); normalized=normalize_conversation_text(raw); text=strip_politeness(raw); entities=detect_entities(raw); products=[e["canonical_name"] for e in entities["products"]]; processes=[e["canonical_name"] for e in entities["processes"]]
    if text in SOCIAL: decision=RouteDecision("social","social_message",1.0)
    elif urls: decision=RouteDecision("explicit_source","explicit_url",1.0,use_retrieval=True,use_llm=True,metadata={"urls":urls})
    elif matches(ESCALATION,text): decision=RouteDecision("escalation","explicit_escalation",1.0,inherit_context=state.technical_case.is_active)
    elif re.search(r"\bahora (?:quiero|necesito) (?:consultar|preguntar|hablar) (?:otro|otra)\b",text): decision=RouteDecision("clarification","explicit_topic_shift_without_subject",0.98,needs_clarification=True)
    elif is_case_update_candidate(raw,state):
        updates,derived=infer_updates(raw);apply_updates(state,updates,derived);decision=RouteDecision("case_update","active_case_update",0.9,inherit_context=True,case_updates=updates,metadata=derived)
    elif matches(CAPABILITY,text): decision=RouteDecision("capabilities","capability_request",1.0)
    elif matches(INTAKE,text): state.technical_case.status="intake";decision=RouteDecision("support_intake","generic_support_request",1.0)
    elif matches(FOLLOW,text):
        if topic_count(state)>1: decision=RouteDecision("clarification","ambiguous_follow_up_referent",0.98,needs_clarification=True)
        elif topic_count(state)==1: decision=RouteDecision("technical_follow_up","single_topic_follow_up",0.9,use_retrieval=True,use_llm=True,inherit_context=True)
        else: decision=RouteDecision("clarification","follow_up_without_topic",0.98,needs_clarification=True)
    elif text in {"como asi","no entiendo","explicame mejor"}: decision=RouteDecision("clarification","request_to_explain_previous_response",0.9,inherit_context=bool(state.conversation.last_route))
    elif products or processes: decision=RouteDecision("technical_query","explicit_registered_entity",0.98,use_retrieval=True,use_llm=True)
    elif looks_technical(text):
        if re.search(r"\bno (?:imprime|funciona|responde)\b",text) and len(text.split())<=6: decision=RouteDecision("clarification","underspecified_technical_symptom",0.95,needs_clarification=True)
        else: decision=RouteDecision("technical_query","self_contained_technical_request",0.85,use_retrieval=True,use_llm=True)
    else: decision=RouteDecision("out_of_scope","no_supported_signal",0.8)
    decision.detected_products=products; decision.detected_processes=processes
    if products or processes:
        state.topic.products=products; state.topic.processes=processes
        if state.technical_case.status in {"idle","intake"} and decision.route=="technical_query": state.technical_case.status="diagnosing"
    decision.metadata.setdefault("normalized_text",normalized); decision.metadata.setdefault("route_text",text)
    decision.deterministic_response=build_response(decision,state); state.conversation.last_route=decision.route; state.turn_number+=1
    return decision
