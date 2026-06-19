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

def build_real_source_labels(docs: list) -> list[str]:
    """
    Create a unique ordered list of real source labels from retrieved docs.
    """
    labels = []
    for doc in docs:
        label = format_source_label(doc.metadata)
        if label not in labels:
            labels.append(label)
    return labels

def build_source_block(real_source_labels: list[str]) -> str:
    if not real_source_labels:
        return "No matching sources available."

    return "\n".join(f"- {label}" for label in real_source_labels)

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

def compute_keyword_overlap_ratio(query: str, content: str) -> float:
    query_tokens = [tok for tok in re.findall(r"\w+", query.lower()) if len(tok) > 2]
    if not query_tokens:
        return 0.0

    overlap = sum(1 for tok in query_tokens if tok in content.lower())
    return overlap / max(len(query_tokens), 1)

def assess_retrieval_support(query: str, docs: list) -> dict:
    """
    Determine whether the retrieved context is strong enough to answer
    only with RAG, or whether a controlled fallback may be needed.
    """
    if not docs:
        return {
            "support_level": "none",
            "top_score": 0.0,
            "avg_overlap": 0.0,
        }

    scores = [compute_rerank_score(query, doc) for doc in docs]
    overlaps = [compute_keyword_overlap_ratio(query, doc.page_content) for doc in docs]

    top_score = max(scores) if scores else 0.0
    avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0.0

    if top_score >= 6.0 and avg_overlap >= 0.15:
        support_level = "strong"
    elif top_score >= 4.0 and avg_overlap >= 0.08:
        support_level = "partial"
    else:
        support_level = "weak"

    return {
        "support_level": support_level,
        "top_score": round(top_score, 3),
        "avg_overlap": round(avg_overlap, 3),
    }
def classify_query_intent(user_query: str) -> str:
    """
    Classify the query into:
    - conceptual
    - requirements
    - procedural
    - troubleshooting
    """
    text = user_query.lower()

    requirements_patterns = [
        "qué requerimientos",
        "que requerimientos",
        "qué requisitos",
        "que requisitos",
        "requerimientos necesarios",
        "requisitos necesarios",
        "system requirements",
        "minimum requirements",
        "requisitos mínimos",
        "requisitos minimos",
    ]

    procedural_patterns = [
        "cómo instalar",
        "como instalar",
        "cómo agregar",
        "como agregar",
        "cómo incorporar",
        "como incorporar",
        "cómo configurar",
        "como configurar",
        "cómo habilitar",
        "como habilitar",
        "cómo crear",
        "como crear",
    ]

    troubleshooting_patterns = [
        "qué hacer si",
        "que hacer si",
        "error",
        "falla",
        "cola",
        "atasco",
        "offline",
        "desaparecen trabajos",
        "disappearing",
        "stuck",
        "not held",
        "cannot add",
        "no puedo",
        "no deja",
    ]

    conceptual_patterns = [
        "qué es",
        "que es",
        "para qué sirve",
        "para que sirve",
        "cómo funciona",
        "como funciona",
        "qué hace",
        "que hace",
        "explica",
        "diferencia entre",
    ]

    if any(pattern in text for pattern in requirements_patterns):
        return "requirements"

    if any(pattern in text for pattern in procedural_patterns):
        return "procedural"

    if any(pattern in text for pattern in troubleshooting_patterns):
        return "troubleshooting"

    if any(pattern in text for pattern in conceptual_patterns):
        return "conceptual"

    return "procedural"

def has_hard_documentary_anchor(user_query: str, docs: list, query_intent: str) -> bool:
    """
    Determine whether the retrieved docs contain enough concrete support
    for the current type of query.
    """
    if not docs:
        return False

    text = user_query.lower()

    query_terms = []
    if "papercut" in text:
        query_terms.append("papercut")
    if "hp" in text:
        query_terms.append("hp")
    if "sds" in text:
        query_terms.append("sds")
    if "web jet admin" in text or "web jetadmin" in text:
        query_terms.append("web jetadmin")
    if "oxp" in text:
        query_terms.append("oxp")
    if "monitor" in text:
        query_terms.append("monitor")

    procedural_terms = [
        "install",
        "instal",
        "configure",
        "configur",
        "add",
        "agreg",
        "incorpor",
        "device",
        "printer",
        "queue",
        "embedded",
        "release",
        "authentication",
        "oxp",
    ]

    troubleshooting_terms = [
        "error",
        "issue",
        "problem",
        "troubleshoot",
        "stuck",
        "missing",
        "queue",
        "print jobs",
        "device",
        "offline",
        "not held",
    ]

    requirements_terms = [
        "requirement",
        "requirements",
        "requer",
        "requisitos",
        "requerimientos",
        "minimum",
        "system requirements",
        "hardware",
        "ram",
        "disk",
        "os",
        "windows",
        "server",
        "vmware",
        "hyperv",
        "cpu",
    ]

    for doc in docs:
        content = doc.page_content.lower()
        meta = doc.metadata

        meta_text = str(meta).lower()
        title_text = str(meta.get("title", "")).lower()
        product = str(meta.get("product", "")).lower()
        component = str(meta.get("component", "")).lower()
        document_family = str(meta.get("document_family", "")).lower()
        source_name = str(meta.get("source", "")).lower()

        query_match = any(term in content or term in title_text or term in meta_text for term in query_terms) if query_terms else True

        if query_intent == "requirements":
            # For requirements, be more permissive and trust requirement-like metadata strongly
            metadata_requirements_match = (
                document_family == "requirements"
                or component == "requirements"
                or "requirements" in title_text
                or "requer" in title_text
                or "requirements" in source_name
                or "requer" in source_name
            )

            content_requirements_match = any(term in content for term in requirements_terms)

            product_match = product in {"sds", "web_jetadmin", "hp_access_control", "gav_tracking"} or "sds" in meta_text

            if product_match and (metadata_requirements_match or content_requirements_match):
                return True

            if query_match and content_requirements_match:
                return True

        elif query_intent == "procedural":
            action_match = any(term in content for term in procedural_terms)
            if query_match and action_match:
                return True

        elif query_intent == "troubleshooting":
            action_match = any(term in content for term in troubleshooting_terms)
            if query_match and action_match:
                return True

        elif query_intent == "conceptual":
            if query_match:
                return True

    return False

def is_explicit_follow_up_query(user_query: str) -> bool:
    """
    Detect whether the user is clearly referring to the previous turn.
    """
    text = user_query.lower().strip()

    follow_up_patterns = [
        "y eso",
        "y como",
        "y cómo",
        "eso",
        "lo anterior",
        "esa herramienta",
        "ese software",
        "ese sistema",
        "ese producto",
        "tambien",
        "también",
        "y en ese caso",
        "y para eso",
    ]

    return any(pattern in text for pattern in follow_up_patterns)

def should_use_memory_for_query(user_query: str, query_intent: str) -> bool:
    """
    Reduce memory contamination:
    - conceptual queries usually should not inherit previous operational context
    - requirements queries usually should not inherit previous questions either
    - only keep memory if the user explicitly refers to previous context
    """
    if is_explicit_follow_up_query(user_query):
        return True

    if query_intent in {"conceptual", "requirements"}:
        return False

    return True

def is_low_risk_general_query(user_query: str) -> bool:
    """
    Allow controlled general fallback only for lower-risk queries,
    such as definitions, concepts, basic explanations, or general guidance.
    """
    text = user_query.lower()

    low_risk_patterns = [
        "qué es",
        "que es",
        "para qué sirve",
        "para que sirve",
        "cómo funciona",
        "como funciona",
        "explica",
        "diferencia entre",
        "requerimientos",
        "requisitos",
        "monitor",
        "qué hace",
        "que hace",
    ]

    return any(pattern in text for pattern in low_risk_patterns)

def should_use_general_fallback(user_query: str, support_info: dict) -> bool:
    """
    Only conceptual queries may use controlled general fallback.
    Procedural and troubleshooting queries must remain grounded.
    """
    intent = classify_query_intent(user_query)

    if intent != "conceptual":
        return False

    if support_info["support_level"] == "strong":
        return False

    return True
    
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

def field_accepts_no_value(field_name: str) -> bool:
    """
    Only optional/enrichment fields should accept explicit 'no value' answers.
    """
    return field_name in {
        "software_version",
        "contract_client_location",
        "evidence",
        "impact_type",
    }
# -----------------------------------------------------------------------------
# Prompting + generation
# -----------------------------------------------------------------------------
SYSTEM_PROMPT = """
Eres Arus PrintAssist, un asistente especializado exclusivamente en soporte de primer nivel para servicios de impresión.

Tu función es:
- responder preguntas sobre impresoras, software de impresión y herramientas del servicio,
- orientar diagnósticos básicos de primer nivel,
- usar la base documental disponible como fuente principal,
- ayudar a estructurar un resumen de incidente si el caso requiere escalamiento.

Debes seguir estrictamente estas reglas:
- Responde únicamente sobre temas relacionados con impresión, software de impresión, herramientas del servicio y procedimientos técnicos.
- No respondas preguntas fuera de alcance.
- No inventes procedimientos críticos si la información disponible no es suficiente.
- Si la información documental no soporta claramente una respuesta, dilo de forma breve y profesional.
- No inventes nombres de fuentes.
- Solo puedes citar las fuentes exactas que te hayan sido proporcionadas en la lista de fuentes disponibles.
- No uses expresiones genéricas como "Documentación oficial de..." salvo que aparezcan literalmente en las fuentes disponibles.
- No menciones RAG, contexto recuperado, fallback, modelo ni arquitectura interna.
- Responde en español.
- Mantén un tono cordial, claro, profesional y orientado a resolver la necesidad del usuario.
- La respuesta debe priorizar utilidad práctica y trazabilidad real.
"""

def build_rag_messages(
    user_query: str,
    retrieved_context: str,
    memory_text: str,
    support_level: str = "strong",
    allow_general_fallback: bool = False,
    real_source_labels: list[str] | None = None,
):
    real_source_labels = real_source_labels or []
    source_block = build_source_block(real_source_labels)

    if allow_general_fallback:
        fallback_instruction = """
Puedes complementar de forma prudente con orientación general solo si:
- la pregunta es de bajo riesgo,
- el contexto documental es parcial,
- y la explicación adicional no inventa procedimientos específicos.

Si complementas, NO lo expliques como proceso interno.
"""
    else:
        fallback_instruction = """
Debes basar la respuesta principalmente en la información documental disponible.
Si la información no es suficiente para responder con precisión, no inventes pasos críticos.
"""

    user_content = f"""
### MEMORIA CORTA DE LA CONVERSACIÓN
{memory_text}

### INFORMACIÓN DOCUMENTAL DISPONIBLE
{retrieved_context}

### FUENTES DISPONIBLES PARA CITAR
{source_block}

### PREGUNTA DEL USUARIO
{user_query}

### NIVEL DE SOPORTE DOCUMENTAL
{support_level}

### FORMATO DE RESPUESTA
Responde usando exactamente esta estructura:

Respuesta:
- Da una respuesta clara, útil y orientada a resolver la necesidad del usuario.

Fuente(s):
- Incluye únicamente fuentes de la lista "FUENTES DISPONIBLES PARA CITAR".
- Si la respuesta no tiene suficiente respaldo documental directo, escribe:
- Base de conocimiento actual sin coincidencias documentales suficientes

### REGLAS DE ESTILO
- No menciones limitaciones salvo que sea realmente necesario.
- Si hace falta advertir algo importante, añade solo una línea final como:
Aviso: ...
- No expliques tu proceso interno.
- No menciones contexto recuperado, RAG, fallback ni modelo.
- No inventes nombres de fuente.
- No cites "Documentación oficial de ..." si no aparece exactamente en la lista de fuentes disponibles.

### INSTRUCCIÓN ADICIONAL
{fallback_instruction}
"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    return messages
    
def clean_user_facing_answer(answer: str) -> str:
    """
    Clean the final answer so the user sees a simpler and more natural output.
    - Remove explicit internal-style sections like 'Limitación:' or 'Nota:'
    - Convert them into a short 'Aviso:' line only when useful
    """
    text = answer.strip()

    # Normalize heading variants
    text = re.sub(r"^\s*nota\s*:\s*", "Aviso: ", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"^\s*limitaci[oó]n\s*:\s*", "Aviso: ", text, flags=re.IGNORECASE | re.MULTILINE)

    # Remove repeated blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # If multiple "Aviso:" lines exist, keep them but make formatting compact
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned_lines = []

    aviso_buffer = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            cleaned_lines.append("")
            continue

        if stripped.lower().startswith("aviso:"):
            aviso_buffer.append(stripped)
        else:
            cleaned_lines.append(line)

    # Keep only one compact aviso block at the end if any aviso exists
    final_text = "\n".join(cleaned_lines).strip()

    if aviso_buffer:
        unique_avisos = []
        for aviso in aviso_buffer:
            if aviso not in unique_avisos:
                unique_avisos.append(aviso)

        final_text += "\n\n" + "\n".join(unique_avisos)

    # Final tidy-up
    final_text = re.sub(r"\n{3,}", "\n\n", final_text).strip()

    return final_text
def answer_uses_fake_generic_sources(answer: str) -> bool:
    generic_patterns = [
        "documentación oficial de",
        "documentacion oficial de",
        "official documentation of",
    ]
    text = answer.lower()
    return any(pattern in text for pattern in generic_patterns)


def enforce_real_source_traceability(answer: str, real_source_labels: list[str], support_info: dict, user_query: str) -> str:
    """
    Always rebuild the source section from real retrieved labels only.
    Never trust the model to invent source names.
    """
    text = answer.strip()

    # Extract avisos if present
    aviso_lines = []
    for line in text.splitlines():
        if line.strip().lower().startswith("aviso:"):
            aviso_lines.append(line.strip())

    # Keep only the core response before any 'Fuente(s):'
    split_parts = re.split(r"\n\s*fuente\(s\)\s*:\s*", text, flags=re.IGNORECASE)
    response_part = split_parts[0].strip()

    # Build trusted source block
    if support_info["support_level"] == "weak":
        source_block = "Fuente(s):\n- Base de conocimiento actual sin coincidencias documentales suficientes"
    else:
        if real_source_labels:
            source_block = "Fuente(s):\n" + "\n".join(f"- {label}" for label in real_source_labels[:3])
        else:
            source_block = "Fuente(s):\n- Base de conocimiento actual sin coincidencias documentales suficientes"

    final_text = f"{response_part}\n\n{source_block}"

    if aviso_lines:
        unique_avisos = []
        for aviso in aviso_lines:
            if aviso not in unique_avisos:
                unique_avisos.append(aviso)
        final_text += "\n\n" + "\n".join(unique_avisos)

    return final_text.strip()

def build_conservative_no_support_answer(user_query: str, real_source_labels: list[str] | None = None) -> str:
    """
    Conservative answer for weak support on non-low-risk questions.
    """
    source_block = "- Base de conocimiento actual sin coincidencias documentales suficientes"
    if real_source_labels:
        source_block = "\n".join(f"- {label}" for label in real_source_labels[:2])

    return f"""Respuesta:
No encontré información suficientemente específica y confiable en la base de conocimiento actual para responder con precisión a esta consulta. Si se trata de una tarea operativa o de configuración, te recomiendo validar con documentación adicional o escalar el caso si el impacto lo requiere.

Fuente(s):
{source_block}

Aviso: La base documental actual no ofrece soporte suficientemente claro para dar un procedimiento preciso."""

def extract_requirement_sentences_from_docs(docs: list, max_sentences: int = 8) -> list:
    """
    Extract requirement-like lines from retrieved requirement documents.
    The goal is to produce grounded, concise answers without relying only on free generation.
    """
    candidate_lines = []

    requirement_keywords = [
        "windows",
        "server",
        "ram",
        "disk",
        "ghz",
        "hyperv",
        "vmware",
        "cpu",
        "x86",
        "x64",
        "icmp",
        "ping",
        "requisitos",
        "requirements",
        "hardware",
        "espacio",
        "memoria",
        "sistema operativo",
        "virtual",
        "nic",
        "red",
    ]

    for doc in docs:
        content = doc.page_content.splitlines()

        for line in content:
            line_clean = " ".join(line.strip().split())

            if len(line_clean) < 15:
                continue

            if any(keyword in line_clean.lower() for keyword in requirement_keywords):
                if line_clean not in candidate_lines:
                    candidate_lines.append(line_clean)

    return candidate_lines[:max_sentences]


def build_requirements_answer_from_docs(user_query: str, docs: list) -> str:
    """
    Build a grounded answer for requirements-oriented queries using only retrieved documents.
    """
    source_labels = build_real_source_labels(docs)
    requirement_lines = extract_requirement_sentences_from_docs(docs)

    if not requirement_lines:
        return build_conservative_no_support_answer(
            user_query=user_query,
            real_source_labels=source_labels,
        )

    bullet_lines = "\n".join(f"- {line}" for line in requirement_lines[:6])

    source_block = (
        "Fuente(s):\n" + "\n".join(f"- {label}" for label in source_labels[:3])
        if source_labels
        else "Fuente(s):\n- Base de conocimiento actual sin coincidencias documentales suficientes"
    )

    return f"""Respuesta:
Con base en la documentación disponible, estos son algunos de los requisitos relevantes identificados para la consulta:

{bullet_lines}

{source_block}"""

def generate_answer_with_rag(user_query: str, memory):
    hf_client = get_hf_client()

    if hf_client is None:
        return (
            "No fue posible generar la respuesta porque falta la configuración "
            "del servicio de inferencia."
        )

    retrieved_context, retrieved_docs = retrieve_context(
        user_query,
        top_k=CONFIG["retrieval_top_k"]
    )

    support_info = assess_retrieval_support(user_query, retrieved_docs)
    real_source_labels = build_real_source_labels(retrieved_docs)

    query_intent = classify_query_intent(user_query)
    allow_general_fallback = should_use_general_fallback(user_query, support_info)
    hard_anchor = has_hard_documentary_anchor(user_query, retrieved_docs, query_intent)

    # -------------------------------------------------------------------------
    # Special grounded path for requirements queries
    # -------------------------------------------------------------------------
    if query_intent == "requirements":
        if hard_anchor:
            answer = build_requirements_answer_from_docs(
                user_query=user_query,
                docs=retrieved_docs,
            )
            memory.add_turn(user_query, answer)
            return answer
        else:
            answer = build_conservative_no_support_answer(
                user_query=user_query,
                real_source_labels=real_source_labels,
            )
            memory.add_turn(user_query, answer)
            return answer

    # -------------------------------------------------------------------------
    # Hard grounding rules for procedural and troubleshooting queries
    # -------------------------------------------------------------------------
    if query_intent in {"procedural", "troubleshooting"} and not hard_anchor:
        answer = build_conservative_no_support_answer(
            user_query=user_query,
            real_source_labels=real_source_labels,
        )
        memory.add_turn(user_query, answer)
        return answer

    if support_info["support_level"] == "weak" and query_intent != "conceptual":
        answer = build_conservative_no_support_answer(
            user_query=user_query,
            real_source_labels=real_source_labels,
        )
        memory.add_turn(user_query, answer)
        return answer

    # -------------------------------------------------------------------------
    # Memory control
    # -------------------------------------------------------------------------
    if should_use_memory_for_query(user_query, query_intent):
        memory_text = memory.format_history()
    else:
        memory_text = "No previous conversation."

    messages = build_rag_messages(
        user_query=user_query,
        retrieved_context=retrieved_context,
        memory_text=memory_text,
        support_level=support_info["support_level"],
        allow_general_fallback=allow_general_fallback,
        real_source_labels=real_source_labels,
    )

    response = hf_client.chat_completion(
        messages=messages,
        max_tokens=LLM_CONFIG["max_tokens"],
        temperature=LLM_CONFIG["temperature"]
    )

    answer = response.choices[0].message.content.strip()
    answer = clean_user_facing_answer(answer)
    answer = enforce_real_source_traceability(
        answer=answer,
        real_source_labels=real_source_labels,
        support_info=support_info,
        user_query=user_query,
    )

    memory.add_turn(user_query, answer)

    return answer

def debug_query_diagnostics(user_query: str) -> dict:
    """
    Debug helper for deployed Streamlit app.
    Returns the exact retrieval and grounding view for a query.
    """
    retrieved_context, retrieved_docs = retrieve_context(
        user_query,
        top_k=CONFIG["retrieval_top_k"]
    )

    support_info = assess_retrieval_support(user_query, retrieved_docs)
    query_intent = classify_query_intent(user_query)
    hard_anchor = has_hard_documentary_anchor(user_query, retrieved_docs, query_intent)
    real_source_labels = build_real_source_labels(retrieved_docs)

    docs_summary = []
    for doc in retrieved_docs[:4]:
        docs_summary.append({
            "title": doc.metadata.get("title"),
            "source": doc.metadata.get("source"),
            "vendor": doc.metadata.get("vendor"),
            "product": doc.metadata.get("product"),
            "component": doc.metadata.get("component"),
            "document_family": doc.metadata.get("document_family"),
            "priority": doc.metadata.get("priority"),
        })

    return {
        "query": user_query,
        "query_intent": query_intent,
        "support_info": support_info,
        "hard_anchor": hard_anchor,
        "real_source_labels": real_source_labels,
        "retrieved_docs_summary": docs_summary,
    }

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

def normalize_user_reply(user_message: str) -> str:
    return " ".join(user_message.strip().lower().split())


def is_no_value_answer(user_message: str) -> bool:
    """
    Only treat exact short answers like 'no', 'no aplica', 'desconozco'
    as explicit 'unknown / not available' values.
    """
    text = normalize_user_reply(user_message)
    return text in NO_VALUE_PATTERNS


def is_non_informative_reply(user_message: str) -> bool:
    """
    Detect replies that should not overwrite the pending field.
    """
    text = normalize_user_reply(user_message)
    return text in NON_INFORMATIVE_REPLY_PATTERNS



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
    # Handle explicit "no value" answers ONLY for optional fields
    # -------------------------------------------------------------------------
    if pending_field and field_accepts_no_value(pending_field) and is_no_value_answer(user_message):
        apply_no_value_to_field(state, pending_field)

    # -------------------------------------------------------------------------
    # Handle unhelpful answers like "ya dije" without overwriting data
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
        # Trust the answer strongly when the bot had just asked for a field
        # ---------------------------------------------------------------------
        if pending_field == "software_involved":
            if not extracted["software_involved"]:
                extracted["software_involved"] = user_text

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
            # Always trust the user's reply as the error/symptom if this was asked
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
        # Avoid polluting unrelated fields
        # ---------------------------------------------------------------------
        if pending_field != "printer_data":
            if extracted.get("printer_data") == user_text and not looks_like_specific_printer_data(user_message):
                extracted["printer_data"] = None

        if pending_field != "error_description":
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
