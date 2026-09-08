from __future__ import annotations

PIPELINE_TERMS = (
    "documentación aprobada", "lista de documentación aprobada", "extracto aprobado",
    "supported_claims", "directrices de este agente", "objetivo documental",
)

HYBRID_ANSWER_INSTRUCTIONS = [
    "Responde primero la necesidad concreta del usuario, no describas el funcionamiento interno del agente.",
    "Usa toda la información explícita de los fragmentos documentales aplicables.",
    "Si la documentación solo cubre una parte, añade orientación complementaria basada en conocimiento general del modelo.",
    "Introduce esa sección como 'Orientación complementaria, no confirmada por las fuentes recuperadas'.",
    "La orientación complementaria puede explicar conceptos, posibilidades y navegaciones probables, pero no debe presentar rutas exactas, valores, compatibilidades o procedimientos delicados como confirmados.",
    "No conviertas una ausencia documental en una negativa extensa. Declara la limitación en una frase y entrega la orientación útil disponible.",
    "No uses lenguaje interno como documentación aprobada, extracto aprobado, claims, juez o pipeline.",
    "Para una pregunta amplia, integra todos los requisitos recuperados en una sola respuesta organizada por categorías.",
]

def answer_mode(citable, coverage_complete: bool) -> str:
    if citable and coverage_complete:
        return "grounded"
    if citable:
        return "grounded_plus_guarded_knowledge"
    return "guarded_internal_knowledge"

def knowledge_flags(mode: str, warning_shown: bool) -> dict:
    used = mode in {"grounded_plus_guarded_knowledge", "guarded_internal_knowledge"}
    return {
        "knowledge_used": used,
        "internal_knowledge_used": used,
        "internal_knowledge_warning_shown": bool(used and warning_shown),
    }

def sanitize_visible_answer(text: str) -> str:
    out = str(text or "").strip()
    replacements = {
        "documentación aprobada": "documentación disponible",
        "lista de documentación aprobada": "documentación recuperada",
        "extracto aprobado": "fragmento recuperado",
        "directrices de este agente": "criterios de confiabilidad",
        "objetivo documental": "búsqueda documental",
    }
    for old, new in replacements.items():
        out = out.replace(old, new).replace(old.capitalize(), new.capitalize())
    return out
