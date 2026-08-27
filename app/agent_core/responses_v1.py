from __future__ import annotations
from app.agent_core.router_models import RouteDecision, RouterShadowState


def build_response(decision: RouteDecision, state: RouterShadowState) -> str | None:
    route=decision.route
    route_text=str(decision.metadata.get("route_text") or decision.metadata.get("normalized_text") or "")
    if route=="social":
        if route_text in {"gracias","muchas gracias"}: return "Con gusto. Si necesitas revisar otro punto del servicio de impresión, puedes indicármelo."
        if route_text in {"ok","listo","entendido"}: return "De acuerdo. Puedes continuar con la información del caso o realizar una nueva consulta."
        if route_text in {"adios","hasta luego"}: return "Hasta luego. Cuando necesites apoyo con el servicio de impresión, estaré disponible."
        return "Hola. Soy Arus PrintAssist. Puedo orientarte en consultas, diagnósticos y procesos relacionados con el servicio de impresión. ¿En qué necesitas ayuda?"
    if route=="capabilities":
        return ("Puedo ayudarte a consultar documentación, orientar troubleshooting inicial, "
                "explicar herramientas y procedimientos de impresión, y preparar un escalamiento técnico. "
                "Para comenzar, indícame la necesidad, el síntoma o el proceso que deseas revisar.")
    if route=="support_intake":
        return ("Claro. Cuéntame qué necesitas revisar. Si se trata de una falla, comparte el síntoma, "
                "el entorno afectado y las validaciones que ya realizaste.")
    if route=="case_update":
        if decision.metadata.get("resolution_status")=="unresolved":
            return "Entendido. Registraré que la validación no resolvió el caso y continuaré desde el contexto ya recopilado."
        if decision.metadata.get("resolution_status")=="resolved":
            return "Entendido. Registraré que la validación resolvió el caso."
        return "Entendido. Incorporé esta información al caso técnico activo."
    if route=="clarification":
        if decision.reason=="ambiguous_follow_up_referent": return "Necesito precisar a cuál de los productos, herramientas o procesos mencionados te refieres."
        if decision.reason=="underspecified_technical_symptom": return "Para orientarte necesito identificar el entorno afectado, el equipo o cola involucrada, el mensaje visible y el alcance de la afectación."
        if decision.reason=="explicit_topic_shift_without_subject": return "De acuerdo. Indícame cuál es el nuevo producto, herramienta, proceso o necesidad que deseas consultar."
        if decision.reason=="request_to_explain_previous_response": return "Claro. Indícame qué parte de la respuesta anterior deseas que explique con mayor detalle."
        if decision.reason=="follow_up_without_topic": return "Necesito un poco más de contexto. Indícame a qué producto, herramienta o proceso te refieres."
        return "Necesito una precisión adicional para continuar sin asumir información."
    if route=="out_of_scope":
        return "Puedo ayudarte con consultas y procesos relacionados con el servicio de impresión. Si tu necesidad está vinculada con este servicio, descríbeme el contexto."
    return None
