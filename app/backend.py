# app/backend.py
# Backend bridge for Arus PrintAssist Streamlit app

from __future__ import annotations

import os
#os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python

import json
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
from huggingface_hub import InferenceClient
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import CONFIG, LLM_CONFIG, RUNTIME_DIR
from app.session_state import ChatSessionState


# -----------------------------------------------------------------------------
# Incident state
# -----------------------------------------------------------------------------
class IncidentState:
    def __init__(self):
        self.software_involved = None
        self.software_version = None
        self.actions_attempted = []
        self.error_description = None
        self.printer_data = None
        self.contract_client_location = None
        self.evidence = None
        self.impact_type = None
        self.escalation_requested = False

    def to_dict(self):
        return {
            "software_involved": self.software_involved,
            "software_version": self.software_version,
            "actions_attempted": self.actions_attempted,
            "error_description": self.error_description,
            "printer_data": self.printer_data,
            "contract_client_location": self.contract_client_location,
            "evidence": self.evidence,
            "impact_type": self.impact_type,
            "escalation_requested": self.escalation_requested,
        }


# -----------------------------------------------------------------------------
# Streamlit resource loading
# -----------------------------------------------------------------------------
@st.cache_resource
def get_embedding_model():
    return HuggingFaceEmbeddings(
        model_name=CONFIG["embedding_model_name"]
    )


@st.cache_resource
def get_vectorstore():
    vectorstore_dir = CONFIG["vectorstore_dir"]

    if not Path(vectorstore_dir).exists():
        raise FileNotFoundError(
            f"Vector store directory not found: {vectorstore_dir}. "
            "Please copy the persistent Chroma index into data/vectorstore "
            "or adjust CONFIG['vectorstore_dir']."
        )

    return Chroma(
        persist_directory=vectorstore_dir,
        embedding_function=get_embedding_model(),
    )


@st.cache_resource
def get_hf_client():
    hf_token = st.secrets.get("HF_TOKEN", None)

    if hf_token is None:
        return None

    return InferenceClient(
        model=LLM_CONFIG["model_name"],
        token=hf_token
    )


def backend_is_ready() -> bool:
    try:
        _ = get_vectorstore()
        _ = get_embedding_model()
        # HF client can be optional during initial UI testing
        return True
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Session state helpers
# -----------------------------------------------------------------------------
def create_chat_session_state() -> ChatSessionState:
    state = ChatSessionState()
    state.incident_state = IncidentState()
    return state


def reset_chat_session_state() -> ChatSessionState:
    return create_chat_session_state()


# -----------------------------------------------------------------------------
# Scope control
# -----------------------------------------------------------------------------
PRINT_SCOPE_KEYWORDS = [
    "impresora",
    "printer",
    "papercut",
    "sds",
    "hp",
    "epson",
    "web jetadmin",
    "cola de impresión",
    "cola de impresion",
    "cola",
    "spooler",
    "driver",
    "firmware",
    "escaner",
    "scanner",
    "toner",
    "impresión",
    "impresion",
]

SUPPORT_FLOW_KEYWORDS = [
    "escalar",
    "nivel 2",
    "abrir caso",
    "incidente",
    "ticket",
    "no funcionó",
    "no funciona",
    "sigue igual",
    "sigue fallando",
    "ya hice eso",
    "ya lo intenté",
    "ya intenté",
    "ya reinicié",
    "ya reinicie",
    "no se resolvió",
]

OUT_OF_SCOPE_RESPONSE = (
    "Solo puedo ayudar con temas relacionados con el servicio de impresión, "
    "como diagnóstico, documentación, uso de herramientas "
    "y escalamiento de incidentes."
)


def is_in_scope_message(user_message: str) -> bool:
    text = user_message.lower()

    domain_match = any(keyword in text for keyword in PRINT_SCOPE_KEYWORDS)
    support_flow_match = any(keyword in text for keyword in SUPPORT_FLOW_KEYWORDS)

    return domain_match or support_flow_match


# -----------------------------------------------------------------------------
# Retrieval helpers
# -----------------------------------------------------------------------------
def format_source_label(metadata: dict) -> str:
    source = metadata.get("source", "unknown_source")
    page = metadata.get("page_label", metadata.get("page", "n/a"))
    title = metadata.get("title", "")

    source_name = Path(source).name if "/" in str(source) else str(source)

    if title:
        return f"{title} | {source_name} | page {page}"
    return f"{source_name} | page {page}"


def make_chroma_filter(**kwargs):
    clauses = [{k: v} for k, v in kwargs.items() if v is not None]

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def detect_query_profile(query: str):
    text = query.lower()

    profile = {
        "k_initial": 12,
        "k_final": 4,
        "filter": None,
    }

    # PaperCut-oriented
    if any(term in text for term in [
        "papercut",
        "trabajos de impresión",
        "trabajos de impresion",
        "print jobs",
        "find-me",
        "mobility print",
    ]):
        profile["filter"] = make_chroma_filter(
            vendor="papercut",
            source_group="core_support"
        )
        return profile

    # SDS / HP-oriented
    if any(term in text for term in [
        "sds",
        "dca",
        "sda",
        "jamc",
        "hp smart device services",
    ]):
        profile["filter"] = make_chroma_filter(
            vendor="hp",
            source_group="core_support"
        )
        return profile

    # Queue / print blocking style issues
    if any(term in text for term in [
        "cola",
        "queue",
        "bloqueada",
        "atascada",
        "atasco",
        "no imprime",
    ]):
        profile["filter"] = make_chroma_filter(
            source_group="core_support",
            priority=1
        )
        return profile

    return profile


def compute_rerank_score(query: str, doc):
    text = query.lower()
    content = doc.page_content.lower()
    metadata = doc.metadata

    score = 0.0

    priority = metadata.get("priority", 3)
    score += max(0, 5 - priority)

    source_type = metadata.get("source_type", "")
    if source_type in {"pdf", "troubleshooting", "known_issue"}:
        score += 2.0
    elif source_type == "kb_article":
        score += 1.0
    elif source_type == "manual":
        score += 0.5

    title = str(metadata.get("title", "")).lower()
    if "temporarily hidden message" in title:
        score += 2.0
    if "known issues" in title:
        score -= 1.5
    if "end user articles" in title:
        score -= 2.0
    if "knowledge base" in title:
        score -= 2.0
    if "troubleshooting articles" in title:
        score -= 2.0

    query_tokens = [tok for tok in re.findall(r"\w+", text) if len(tok) > 2]
    overlap = sum(1 for tok in query_tokens if tok in content)
    score += overlap * 0.4

    if "dca" in text:
        if "dca" in content:
            score += 2.0
        if "sda" in content and "dca" not in content:
            score -= 1.5

    if "papercut" in text and metadata.get("vendor") == "papercut":
        score += 2.0

    if "trabajos" in text or "print jobs" in text:
        if "print jobs" in content or "trabajos" in content or "release" in content:
            score += 1.5

    if "cola" in text or "bloqueada" in text:
        if "cola" in content or "queue" in content or "bloqueada" in content:
            score += 1.5

    return score


def retrieve_context(query: str, top_k: int = 4):
    vectorstore = get_vectorstore()
    profile = detect_query_profile(query)

    filtered_retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": profile["k_initial"],
            "filter": profile["filter"]
        }
    )

    docs = filtered_retriever.invoke(query)

    ranked_docs = sorted(
        docs,
        key=lambda d: compute_rerank_score(query, d),
        reverse=True
    )

    final_docs = ranked_docs[:profile["k_final"]]
    context_blocks = []

    for i, doc in enumerate(final_docs, start=1):
        source_label = format_source_label(doc.metadata)
        content = doc.page_content.strip()

        context_blocks.append(
            f"[Chunk {i}] Source: {source_label}\n{content}"
        )

    return "\n\n".join(context_blocks), final_docs


# -----------------------------------------------------------------------------
# Prompting + generation
# -----------------------------------------------------------------------------
SYSTEM_PROMPT = """
Eres Arus PrintAssist, un asistente especializado exclusivamente en soporte de primer nivel para servicios de impresión.

Tu función es:
- responder preguntas sobre impresoras, software de impresión y herramientas del servicio,
- orientar diagnósticos básicos de primer nivel,
- usar únicamente la información contenida en el contexto recuperado,
- ayudar a estructurar un resumen de incidente si el caso requiere escalamiento.

Debes seguir estrictamente estas reglas:
- Responde únicamente sobre temas relacionados con impresión, software de impresión, herramientas del servicio y procedimientos técnicos.
- No respondas preguntas fuera de alcance.
- No inventes información.
- No completes con conocimiento general si el contexto recuperado no lo respalda claramente.
- Si el contexto no es suficiente para responder con precisión, dilo explícitamente.
- Si la pregunta pide una definición general y el contexto solo contiene instrucciones operativas, indícalo claramente.
- Responde en español.
- Mantén un tono cordial, claro y profesional.
- Cuando sea posible, menciona brevemente la fuente o el tipo de documento usado.
"""


def build_rag_messages(user_query: str, retrieved_context: str, memory_text: str):
    user_content = f"""
### MEMORIA CORTA DE LA CONVERSACIÓN
{memory_text}

### CONTEXTO RECUPERADO
{retrieved_context}

### PREGUNTA DEL USUARIO
{user_query}

### FORMATO DE RESPUESTA
Responde con esta estructura:

Respuesta:
- Explica la respuesta solo con base en el contexto recuperado.

Fuente(s):
- Menciona brevemente el documento o fuente principal utilizada.

Limitación:
- Si el contexto no es suficiente, dilo claramente.
- Si la pregunta requiere una definición general y el contexto solo permite una respuesta parcial, indícalo.
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    return messages


def generate_answer_with_rag(user_query: str, memory):
    hf_client = get_hf_client()

    if hf_client is None:
        return (
            "El backend está listo, pero no se encontró HF_TOKEN en st.secrets. "
            "Configura el secreto en Streamlit Community Cloud para habilitar la generación."
        )

    retrieved_context, retrieved_docs = retrieve_context(
        user_query,
        top_k=CONFIG["retrieval_top_k"]
    )

    memory_text = memory.format_history()
    messages = build_rag_messages(user_query, retrieved_context, memory_text)

    response = hf_client.chat_completion(
        messages=messages,
        max_tokens=LLM_CONFIG["max_tokens"],
        temperature=LLM_CONFIG["temperature"]
    )

    answer = response.choices[0].message.content.strip()
    memory.add_turn(user_query, answer)

    return answer


# -----------------------------------------------------------------------------
# Escalation logic
# -----------------------------------------------------------------------------
ESCALATION_TRIGGERS = [
    "escalar",
    "nivel 2",
    "abrir caso",
    "incidente",
    "ticket",
    "no funcionó",
    "no funciona",
    "sigue igual",
    "sigue fallando",
    "ya hice eso",
    "ya lo intenté",
    "ya intenté",
    "ya reinicié",
    "ya reinicie",
    "no se resolvió",
]


CORE_INCIDENT_FIELDS = [
    "software_involved",
    "error_description",
    "actions_attempted",
    "printer_data",
]

ENRICHMENT_INCIDENT_FIELDS = [
    "software_version",
    "contract_client_location",
    "evidence",
    "impact_type",
]

FIELD_QUESTIONS = {
    "software_involved": "¿Qué software o herramienta de impresión está involucrado en el incidente?",
    "software_version": "¿Conoces la versión del software involucrado? Si la conoces, compártela; si no, escribe 'no'.",
    "actions_attempted": "¿Qué acciones o validaciones ya realizaste antes de este punto?",
    "error_description": "¿Cuál es el error exacto o síntoma principal que estás observando?",
    "printer_data": "¿Qué datos de la impresora puedes compartir (modelo, conexión, ubicación, etc.)?",
    "contract_client_location": "¿Qué cliente, contrato o ubicación está asociado al caso? Si no aplica o no lo conoces, escribe 'no'.",
    "evidence": "¿Deseas adjuntar o describir alguna evidencia, como capturas o mensajes de error? Si no tienes, escribe 'no'.",
    "impact_type": "¿Qué tipo de afectación genera este incidente? Por ejemplo: un usuario, varios usuarios, dispositivo crítico, indisponibilidad total o intermitente.",
}

NO_VALUE_PATTERNS = [
    "no",
    "no aplica",
    "no tengo",
    "desconozco",
    "no sé",
    "no se",
]

NON_INFORMATIVE_REPLY_PATTERNS = [
    "ya te dije",
    "ya lo dije",
    "ya respondí",
    "ya respondi",
    "lo mismo",
    "igual",
]

def is_non_informative_reply(user_message: str) -> bool:
    text = user_message.strip().lower()
    return any(pattern in text for pattern in NON_INFORMATIVE_REPLY_PATTERNS)


def looks_like_specific_printer_data(user_message: str) -> bool:
    text = user_message.lower()

    model_or_device_hint = any(term in text for term in [
        "laserjet",
        "officejet",
        "deskjet",
        "pagewide",
        "multifuncional",
        "mfp",
        "serial",
        "serie",
        "hostname",
        "usb",
        "ethernet",
        "wifi",
        "scanner",
        "escaner",
    ])

    ip_hint = bool(re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", user_message))
    hp_model_hint = bool(re.search(r"\bhp\s+[A-Za-z0-9\-]+\b", user_message, re.IGNORECASE))

    return model_or_device_hint or ip_hint or hp_model_hint
def should_activate_escalation_mode(user_message: str) -> bool:
    text = user_message.lower()
    return any(trigger in text for trigger in ESCALATION_TRIGGERS)

def get_missing_incident_fields(state: IncidentState):
    """
    Ask core fields first. Once core fields are complete,
    continue with enrichment fields.
    """
    missing = []

    for field_name in CORE_INCIDENT_FIELDS:
        value = getattr(state, field_name, None)
        if not value:
            missing.append(field_name)

    # Only ask enrichment once the core block is complete
    if not missing:
        for field_name in ENRICHMENT_INCIDENT_FIELDS:
            value = getattr(state, field_name, None)
            if not value:
                missing.append(field_name)

    return missing

def is_no_value_answer(user_message: str) -> bool:
    text = user_message.strip().lower()
    return any(pattern == text or pattern in text for pattern in NO_VALUE_PATTERNS)


def apply_no_value_to_field(state: IncidentState, field_name: str):
    fallback_values = {
        "software_version": "No especificada por el usuario",
        "contract_client_location": "No especificado por el usuario",
        "evidence": "No adjunta evidencia",
        "impact_type": "No especificado por el usuario",
    }

    if field_name in fallback_values:
        setattr(state, field_name, fallback_values[field_name])

def generate_escalation_followup(state: IncidentState):
    missing = get_missing_incident_fields(state)

    if not missing:
        return None

    return FIELD_QUESTIONS[missing[0]]


KNOWN_SOFTWARE = [
    "hp smart device services",
    "sds",
    "papercut",
    "web jetadmin",
    "hp access control",
    "gav tracking",
]

ACTION_PATTERNS = [
    "reinicié",
    "reinicie",
    "reiniciar",
    "reinstalé",
    "reinstale",
    "actualicé",
    "actualice",
    "verifiqué",
    "verifique",
    "probé",
    "probe",
    "validé",
    "valide",
    "desinstalé",
    "desinstale",
]

ERROR_PATTERNS = [
    "error",
    "falla",
    "bloqueada",
    "no responde",
    "no funciona",
    "cola",
    "atasco",
    "offline",
    "desconectada",
]

VERSION_RE = re.compile(
    r"(?:versi[oó]n|version)\s*[:\-]?\s*([A-Za-z0-9\.\-_]+)",
    re.IGNORECASE
)


def extract_incident_fields(user_message: str):
    text = user_message.lower()

    extracted = {
        "software_involved": None,
        "software_version": None,
        "actions_attempted": [],
        "error_description": None,
        "printer_data": None,
        "contract_client_location": None,
        "evidence": None,
        "impact_type": None,
    }

    # -------------------------------------------------------------------------
    # Detect software + version in compact expressions like:
    # "Papercut MF 25.2"
    # "SDS 7.2"
    # -------------------------------------------------------------------------
    papercut_match = re.search(
        r"\b(papercut(?:\s+(?:mf|ng|hive|pocket|mobility print))?)\s+v?(\d+(?:\.\d+)+)\b",
        user_message,
        re.IGNORECASE
    )
    if papercut_match:
        extracted["software_involved"] = papercut_match.group(1).strip().lower()
        extracted["software_version"] = papercut_match.group(2).strip()

    sds_match = re.search(
        r"\b(hp smart device services|sds|web jetadmin|hp access control|gav tracking)\s+v?(\d+(?:\.\d+)+)\b",
        user_message,
        re.IGNORECASE
    )
    if sds_match:
        extracted["software_involved"] = sds_match.group(1).strip().lower()
        extracted["software_version"] = sds_match.group(2).strip()

    # Detect software by known names if version pattern did not match
    if not extracted["software_involved"]:
        for software in KNOWN_SOFTWARE:
            if software in text:
                extracted["software_involved"] = software
                break

    # Detect version if sentence includes "version" explicitly
    version_match = VERSION_RE.search(user_message)
    if version_match and not extracted["software_version"]:
        extracted["software_version"] = version_match.group(1)

    # Detect attempted actions
    detected_actions = [pattern for pattern in ACTION_PATTERNS if pattern in text]
    if detected_actions:
        extracted["actions_attempted"] = list(set(detected_actions))

    # Detect error / symptom descriptions
    if any(pattern in text for pattern in ERROR_PATTERNS):
        extracted["error_description"] = user_message.strip()

    # Additional symptom patterns without the word "error"
    if any(expr in text for expr in [
        "no puedo",
        "no deja",
        "no me permite",
        "no aparece",
        "no logro",
        "no carga",
        "se detiene",
        "se cae",
        "no registra",
        "no agrega",
        "no detecta",
        "no encuentra",
    ]):
        extracted["error_description"] = user_message.strip()

    # Printer data
    if looks_like_specific_printer_data(user_message):
        extracted["printer_data"] = user_message.strip()

    # Client / contract / location
    if any(term in text for term in [
        "cliente",
        "contrato",
        "sede",
        "ubicación",
        "ubicacion",
        "site",
        "oficina",
    ]):
        extracted["contract_client_location"] = user_message.strip()

    # Evidence
    if any(term in text for term in [
        "captura",
        "screenshot",
        "pantallazo",
        "evidencia",
        "log",
        "adjunto",
        "mensaje de error",
    ]):
        extracted["evidence"] = user_message.strip()

    # Impact
    if any(term in text for term in [
        "afecta",
        "varios usuarios",
        "muchos usuarios",
        "un usuario",
        "todos los usuarios",
        "dispositivo crítico",
        "dispositivo critico",
        "indisponibilidad",
        "intermitente",
        "no imprime",
        "operación detenida",
        "operacion detenida",
    ]):
        extracted["impact_type"] = user_message.strip()

    return extracted
    
def update_incident_state(state: IncidentState, extracted_fields: dict):
    if extracted_fields["software_involved"] and not state.software_involved:
        state.software_involved = extracted_fields["software_involved"]

    if extracted_fields["software_version"] and not state.software_version:
        state.software_version = extracted_fields["software_version"]

    if extracted_fields["error_description"] and not state.error_description:
        state.error_description = extracted_fields["error_description"]

    if extracted_fields["printer_data"] and not state.printer_data:
        state.printer_data = extracted_fields["printer_data"]

    if extracted_fields["contract_client_location"] and not state.contract_client_location:
        state.contract_client_location = extracted_fields["contract_client_location"]

    if extracted_fields["evidence"] and not state.evidence:
        state.evidence = extracted_fields["evidence"]

    if extracted_fields["impact_type"] and not state.impact_type:
        state.impact_type = extracted_fields["impact_type"]

    for action in extracted_fields["actions_attempted"]:
        if action not in state.actions_attempted:
            state.actions_attempted.append(action)

    return state


def build_incident_summary(state: IncidentState) -> str:
    summary = f"""
Resumen del incidente:
- Software involucrado: {state.software_involved or 'No especificado'}
- Versión del software: {state.software_version or 'No especificada'}
- Error o síntoma principal: {state.error_description or 'No especificado'}
- Acciones realizadas: {', '.join(state.actions_attempted) if state.actions_attempted else 'No especificadas'}
- Datos de impresora: {state.printer_data or 'No especificados'}
- Cliente / contrato / ubicación: {state.contract_client_location or 'No especificado'}
- Evidencia: {state.evidence or 'No especificada'}
- Tipo de afectación: {state.impact_type or 'No especificado'}
"""
    return summary.strip()


def process_escalation_turn(user_message: str, state: IncidentState, session_state: ChatSessionState):
    pending_field = getattr(session_state, "pending_incident_field", None)
    user_text = user_message.strip()

    # -------------------------------------------------------------------------
    # If the user answered with "no", "no aplica", etc. for the pending field,
    # store an explicit unavailable value and continue.
    # -------------------------------------------------------------------------
    if pending_field and is_no_value_answer(user_message):
        apply_no_value_to_field(state, pending_field)

    # -------------------------------------------------------------------------
    # If the user gives a non-informative reply like "ya te dije", keep asking
    # for the same pending field instead of moving on.
    # -------------------------------------------------------------------------
    elif pending_field and is_non_informative_reply(user_message):
        return {
            "status": "collecting_information",
            "missing_fields": get_missing_incident_fields(state),
            "next_field": pending_field,
            "next_question": FIELD_QUESTIONS[pending_field],
            "incident_state": state.to_dict(),
        }

    else:
        extracted = extract_incident_fields(user_message)

        # ---------------------------------------------------------------------
        # Trust the user answer for the pending field strongly.
        # This is the key to avoid loops.
        # ---------------------------------------------------------------------
        if pending_field == "software_involved":
            if not extracted["software_involved"]:
                extracted["software_involved"] = user_text

            # If the software phrase also contains a version like "Papercut MF 25.2"
            if not extracted["software_version"]:
                version_only = re.search(r"\b\d+(?:\.\d+)+\b", user_message)
                if version_only:
                    extracted["software_version"] = version_only.group(0)

        elif pending_field == "software_version":
            if not extracted["software_version"]:
                version_only = re.search(r"\b\d+(?:\.\d+)+\b", user_message)
                if version_only:
                    extracted["software_version"] = version_only.group(0)
                else:
                    extracted["software_version"] = user_text

        elif pending_field == "error_description":
            # Always trust the full user answer as the symptom description
            extracted["error_description"] = user_text

        elif pending_field == "actions_attempted":
            extracted["actions_attempted"] = [user_text]

        elif pending_field == "printer_data":
            extracted["printer_data"] = user_text

        elif pending_field == "contract_client_location":
            extracted["contract_client_location"] = user_text

        elif pending_field == "evidence":
            extracted["evidence"] = user_text

        elif pending_field == "impact_type":
            extracted["impact_type"] = user_text

        # ---------------------------------------------------------------------
        # Prevent unrelated fields from being polluted by a reply intended for
        # another pending field.
        # ---------------------------------------------------------------------
        if pending_field != "printer_data":
            if extracted.get("printer_data") == user_text and not looks_like_specific_printer_data(user_message):
                extracted["printer_data"] = None

        if pending_field != "error_description":
            # Keep auto-detected error only if it comes from a real error pattern
            if extracted.get("error_description") == user_text and pending_field == "actions_attempted":
                extracted["error_description"] = None

        update_incident_state(state, extracted)

    missing_fields = get_missing_incident_fields(state)

    if missing_fields:
        next_field = missing_fields[0]
        next_question = FIELD_QUESTIONS[next_field]
        return {
            "status": "collecting_information",
            "missing_fields": missing_fields,
            "next_field": next_field,
            "next_question": next_question,
            "incident_state": state.to_dict(),
        }

    summary = build_incident_summary(state)
    return {
        "status": "ready_for_summary",
        "missing_fields": [],
        "summary": summary,
        "incident_state": state.to_dict(),
    }
# -----------------------------------------------------------------------------
# Logging / persistence
# -----------------------------------------------------------------------------
LOGS_FILE = RUNTIME_DIR / "conversation_logs.json"
INCIDENTS_FILE = RUNTIME_DIR / "incident_summaries.json"


def append_json_record(file_path: Path, record: dict):
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
    else:
        data = []

    data.append(record)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def persist_session_logs(session_state: ChatSessionState):
    timestamp = datetime.now().isoformat()

    for entry in session_state.logs:
        record = {
            "timestamp": timestamp,
            "route_type": entry["route_type"],
            "user_message": entry["user_message"],
            "bot_message": entry["bot_message"],
        }
        append_json_record(LOGS_FILE, record)


def persist_incident_summary(session_state: ChatSessionState):
    record = {
        "timestamp": datetime.now().isoformat(),
        "incident_state": session_state.incident_state.to_dict(),
        "summary_text": build_incident_summary(session_state.incident_state),
    }
    append_json_record(INCIDENTS_FILE, record)


def export_incident_summary_text(session_state: ChatSessionState):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = RUNTIME_DIR / f"incident_summary_{timestamp}.txt"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(build_incident_summary(session_state.incident_state))

    return file_path


def finalize_escalation_case(session_state: ChatSessionState):
    persist_session_logs(session_state)
    persist_incident_summary(session_state)
    exported_file = export_incident_summary_text(session_state)

    return {
        "status": "persisted",
        "exported_file": str(exported_file),
    }

def ensure_session_state_integrity(session_state: ChatSessionState):
    """
    Ensure the session state always has the required backend attributes.
    This prevents failures when an old Streamlit session survives code updates.
    """
    if getattr(session_state, "mode", None) is None:
        session_state.mode = "normal"

    if getattr(session_state, "memory", None) is None:
        from app.session_state import RollingConversationMemory
        session_state.memory = RollingConversationMemory(max_turns=4)

    if getattr(session_state, "logs", None) is None:
        session_state.logs = []

    if getattr(session_state, "incident_state", None) is None:
        session_state.incident_state = IncidentState()

    if getattr(session_state, "pending_incident_field", None) is None:
        session_state.pending_incident_field = None

    return session_state

# -----------------------------------------------------------------------------
# Routing
# -----------------------------------------------------------------------------

def handle_escalation_message(user_message: str, session_state: ChatSessionState):
    session_state = ensure_session_state_integrity(session_state)

    session_state.mode = "escalation"
    session_state.incident_state.escalation_requested = True

    result = process_escalation_turn(
        user_message,
        session_state.incident_state,
        session_state
    )

    if result["status"] == "collecting_information":
        bot_message = result["next_question"]
        session_state.pending_incident_field = result["next_field"]
        session_state.memory.add_turn(user_message, bot_message)
        session_state.log_turn(user_message, bot_message, "escalation_collect")
        return bot_message

    session_state.pending_incident_field = None

    summary = result["summary"]
    bot_message = (
        "He reunido la información principal del caso. "
        "Por favor revisa el siguiente resumen antes de escalar:\n\n"
        f"{summary}\n\n"
        "Si deseas, puedes usar el botón de la barra lateral para finalizar y exportar el caso."
    )

    session_state.memory.add_turn(user_message, bot_message)
    session_state.log_turn(user_message, bot_message, "escalation_summary")
    return bot_message

def handle_normal_message(user_message: str, session_state: ChatSessionState):
    bot_message = generate_answer_with_rag(
        user_query=user_message,
        memory=session_state.memory,
    )

    session_state.log_turn(user_message, bot_message, "rag_answer")
    return bot_message



def route_user_message(user_message: str, session_state: ChatSessionState):
    session_state = ensure_session_state_integrity(session_state)

    # 1. If escalation mode is already active, continue it
    if session_state.mode == "escalation":
        return handle_escalation_message(user_message, session_state)

    # 2. If the message triggers escalation, activate it
    if should_activate_escalation_mode(user_message):
        return handle_escalation_message(user_message, session_state)

    # 3. Scope control
    if not is_in_scope_message(user_message):
        bot_message = OUT_OF_SCOPE_RESPONSE
        session_state.memory.add_turn(user_message, bot_message)
        session_state.log_turn(user_message, bot_message, "out_of_scope")
        return bot_message

    # 4. Normal RAG flow
    return handle_normal_message(user_message, session_state)

def get_backend_status():
    status = {
        "vectorstore_ok": False,
        "embedding_ok": False,
        "hf_client_ok": False,
        "error": None,
    }

    try:
        _ = get_embedding_model()
        status["embedding_ok"] = True
    except Exception as e:
        status["error"] = f"Embedding model error: {e}"
        return status

    try:
        _ = get_vectorstore()
        status["vectorstore_ok"] = True
    except Exception as e:
        status["error"] = f"Vector store error: {e}"
        return status

    try:
        hf_client = get_hf_client()
        status["hf_client_ok"] = hf_client is not None
    except Exception as e:
        status["error"] = f"HF client error: {e}"
        return status

    return status
