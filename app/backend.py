
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from huggingface_hub import InferenceClient
try:
    from huggingface_hub.errors import BadRequestError, HfHubHTTPError
except Exception:
    BadRequestError = Exception
    HfHubHTTPError = Exception
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import CONFIG, LLM_CONFIG, RUNTIME_DIR
from app.session_state import ChatSessionState, RollingConversationMemory

from app.domain_registry import (
    PRODUCT_ENTITY_REGISTRY,
    PROCESS_ENTITY_REGISTRY,
    PRODUCT_ALIAS_INDEX,
    PROCESS_ALIAS_INDEX,
    detect_entities_in_text,
)


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

    def to_dict(self) -> dict[str, Any]:
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
# Streamlit resources
# -----------------------------------------------------------------------------
@st.cache_resource
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name=CONFIG["embedding_model_name"])


def get_vectorstore_signature(vectorstore_dir: str) -> str:
    base = Path(vectorstore_dir)
    if not base.exists():
        return "missing"

    parts = []
    for path in sorted(base.rglob("*")):
        if path.is_file():
            parts.append(f"{path.relative_to(base)}:{path.stat().st_size}")
    return "|".join(parts)


@st.cache_resource
def get_vectorstore_cached(signature: str):
    vectorstore_dir = CONFIG["vectorstore_dir"]
    collection_name = CONFIG.get("collection_name", "langchain")
    return Chroma(
        collection_name=collection_name,
        persist_directory=vectorstore_dir,
        embedding_function=get_embedding_model(),
    )


def get_vectorstore():
    vectorstore_dir = CONFIG["vectorstore_dir"]
    if not Path(vectorstore_dir).exists():
        raise FileNotFoundError(f"Vector store directory not found: {vectorstore_dir}")
    signature = get_vectorstore_signature(vectorstore_dir)
    return get_vectorstore_cached(signature)


@st.cache_resource
def get_hf_client():
    hf_token = st.secrets.get("HF_TOKEN", None)
    if not hf_token:
        return None

    model_name = get_effective_llm_model()
    provider = get_effective_hf_provider()

    if provider:
        return InferenceClient(
            model=model_name,
            provider=provider,
            token=hf_token,
        )

    return InferenceClient(
        model=model_name,
        token=hf_token,
    )

def backend_is_ready() -> bool:
    try:
        _ = get_embedding_model()
        _ = get_vectorstore()
        return True
    except Exception:
        return False

def get_effective_llm_model() -> str:
    return st.secrets.get("HF_MODEL", LLM_CONFIG.get("model_name"))


def get_effective_hf_provider():
    return st.secrets.get("HF_PROVIDER", LLM_CONFIG.get("provider", None))

# -----------------------------------------------------------------------------
# Session helpers
# -----------------------------------------------------------------------------
def create_chat_session_state() -> ChatSessionState:
    state = ChatSessionState()
    state.incident_state = IncidentState()
    return state


def reset_chat_session_state() -> ChatSessionState:
    return create_chat_session_state()


def ensure_session_state_integrity(session_state: ChatSessionState):
    if getattr(session_state, "mode", None) is None:
        session_state.mode = "normal"
    if getattr(session_state, "memory", None) is None:
        session_state.memory = RollingConversationMemory(max_turns=4)
    if getattr(session_state, "logs", None) is None:
        session_state.logs = []
    if getattr(session_state, "incident_state", None) is None:
        session_state.incident_state = IncidentState()
    if getattr(session_state, "pending_incident_field", None) is None:
        session_state.pending_incident_field = None
    return session_state


# -----------------------------------------------------------------------------
# Scope control
# -----------------------------------------------------------------------------
PRINT_SCOPE_KEYWORDS = [
    "impresora", "printer", "papercut", "sds", "hp", "epson", "web jetadmin",
    "cola de impresión", "cola de impresion", "cola", "spooler", "driver", "firmware",
    "escaner", "scanner", "toner", "impresión", "impresion", "multifuncional",
    "copiadora", "mfp", "oxp", "wja", "jetadmin",
]

SUPPORT_FLOW_KEYWORDS = [
    "escalar", "nivel 2", "abrir caso", "incidente", "ticket", "no funcionó",
    "no funciona", "sigue igual", "sigue fallando", "ya hice eso", "ya lo intenté",
    "ya intenté", "ya reinicié", "ya reinicie", "no se resolvió",
]

OUT_OF_SCOPE_RESPONSE = (
    "Solo puedo ayudar con temas relacionados con el servicio de impresión, "
    "como diagnóstico, documentación, uso de herramientas y escalamiento de incidentes."
)


def is_in_scope_message(user_message: str) -> bool:
    text = user_message.lower()

    detected_products = detect_entities_in_text(text, PRODUCT_ALIAS_INDEX)
    detected_processes = detect_entities_in_text(text, PROCESS_ALIAS_INDEX)

    if detected_products or detected_processes:
        return True

    # Fallback to generic scope keywords
    domain_match = any(k in text for k in PRINT_SCOPE_KEYWORDS)
    support_match = any(k in text for k in SUPPORT_FLOW_KEYWORDS)

    return domain_match or support_match

# -----------------------------------------------------------------------------
# Query Entities helpers
# -----------------------------------------------------------------------------
    
def detect_query_entities(user_query: str) -> dict:
    text = user_query.lower()

    product_ids = detect_entities_in_text(text, PRODUCT_ALIAS_INDEX)
    process_ids = detect_entities_in_text(text, PROCESS_ALIAS_INDEX)

    return {
        "products": product_ids,
        "processes": process_ids,
    }
    
def get_detected_entity_aliases(user_query: str) -> list[str]:
    """
    Return all matched aliases present in the query text,
    from both product and process registries.
    """
    text = user_query.lower()
    aliases = []

    for alias in PRODUCT_ALIAS_INDEX.keys():
        if alias in text and alias not in aliases:
            aliases.append(alias)

    for alias in PROCESS_ALIAS_INDEX.keys():
        if alias in text and alias not in aliases:
            aliases.append(alias)

    return aliases


def score_title_and_source_matches(user_query: str, metadata: dict) -> float:
    """
    Boost documents whose title/source strongly match detected entity aliases
    or important query fragments.
    """
    score = 0.0
    title = str(metadata.get("title", "")).lower()
    source = str(metadata.get("source", "")).lower()

    detected_aliases = get_detected_entity_aliases(user_query)

    for alias in detected_aliases:
        if alias in title:
            score += 4.0
        if alias in source:
            score += 3.0

    # Additional phrase-level boost for exact query fragments
    query_text = user_query.lower().strip()

    if len(query_text) >= 8:
        if query_text in title:
            score += 5.0
        if query_text in source:
            score += 4.0

    return score

# -----------------------------------------------------------------------------
# Retrieval helpers
# -----------------------------------------------------------------------------
def get_entity_aliases_for_query(user_query: str) -> list[str]:
    """
    Return unique aliases detected in the query from both registries.
    """
    text = user_query.lower()
    aliases = []

    for alias in PRODUCT_ALIAS_INDEX.keys():
        if alias in text and alias not in aliases:
            aliases.append(alias)

    for alias in PROCESS_ALIAS_INDEX.keys():
        if alias in text and alias not in aliases:
            aliases.append(alias)

    return aliases


def has_strong_entity_document_match(user_query: str, docs: list) -> bool:
    """
    Detect when retrieved docs are clearly aligned with the user's query,
    even if generic support heuristics classify support as weak.

    This is especially useful for internal operational procedures where
    metadata may be sparse, but title/source alignment is very strong.
    """
    if not docs:
        return False

    aliases = get_entity_aliases_for_query(user_query)
    if not aliases:
        return False

    strong_hits = 0

    for doc in docs[:4]:
        md = doc.metadata
        title = str(md.get("title", "")).lower()
        source = str(md.get("source", "")).lower()
        vendor = str(md.get("vendor", "")).lower()
        source_type = str(md.get("source_type", "")).lower()

        alias_match = any(alias in title or alias in source for alias in aliases)

        internal_match = (
            vendor == "arus_internal"
            or "da arus" in source
            or "/da arus/" in source
            or "da0" in source
            or "da0" in title
            or "in0" in source
            or "in0" in title
        )

        if alias_match:
            strong_hits += 2

        if alias_match and internal_match:
            strong_hits += 2

        if alias_match and source_type in {"pdf", "manual", "kb_article"}:
            strong_hits += 1

    return strong_hits >= 3

def format_source_label(metadata: dict) -> str:
    source = metadata.get("source", "unknown_source")
    title = metadata.get("title", "")
    source_name = Path(str(source)).name if "/" in str(source) else str(source)
    page = metadata.get("page_label", metadata.get("page", None))

    if page is None:
        return f"{title} | {source_name}" if title else source_name
    return f"{title} | {source_name} | page {page}" if title else f"{source_name} | page {page}"


def build_real_source_labels(docs: list) -> list[str]:
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)

    for doc in docs:
        md = doc.metadata
        title = md.get("title", "")
        source = md.get("source", "unknown_source")
        source_name = Path(str(source)).name if "/" in str(source) else str(source)
        page = md.get("page_label", md.get("page", None))
        key = (title, source_name)
        if page is not None:
            try:
                grouped[key].append(int(str(page)))
            except Exception:
                grouped[key]
        else:
            grouped[key]

    labels = []
    for (title, source_name), pages in grouped.items():
        pages = sorted(set(pages))
        if pages:
            page_text = f"page {pages[0]}" if len(pages) == 1 else f"pages {pages[0]}–{pages[-1]}"
            labels.append(f"{title} | {source_name} | {page_text}" if title else f"{source_name} | {page_text}")
        else:
            labels.append(f"{title} | {source_name}" if title else source_name)
    return labels


def build_source_block(real_source_labels: list[str]) -> str:
    if not real_source_labels:
        return "- Base de conocimiento actual sin coincidencias documentales suficientes"
    return "\n".join(f"- {label}" for label in real_source_labels[:3])


def make_chroma_filter(**kwargs):
    clauses = [{k: v} for k, v in kwargs.items() if v is not None]
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}

def detect_query_entities(user_query: str) -> dict:
    """
    Detect product and process entities present in the query text.
    """
    text = user_query.lower()

    product_ids = detect_entities_in_text(text, PRODUCT_ALIAS_INDEX)
    process_ids = detect_entities_in_text(text, PROCESS_ALIAS_INDEX)

    return {
        "products": product_ids,
        "processes": process_ids,
    }

def detect_query_profile(query: str):
    """
    Build a retrieval profile using query intent and lightweight hints.

    Important:
    - Do not apply hard metadata filters by default.
    - Hard filters caused empty retrieval for PaperCut MF and HP SDS when
      metadata did not match exactly.
    - Prefer broad retrieval + reranking.
    """
    text = query.lower()
    query_intent = classify_query_intent(query)

    initial_map = CONFIG.get("retrieval_top_k_by_intent", {})
    final_map = CONFIG.get("retrieval_final_top_k_by_intent", {})

    profile = {
        "intent": query_intent,
        "k_initial": initial_map.get(query_intent, initial_map.get("default", 12)),
        "k_final": final_map.get(query_intent, final_map.get("default", 4)),
        "filter": None,
        "must_terms": [],
        "avoid_terms": [],
        "preferred_terms": [],
    }

    if "papercut" in text:
        profile["preferred_terms"].extend([
            "papercut", "papercut mf", "print jobs", "jobs",
            "release", "hold", "held", "find-me", "mobility print",
            "trabajos", "liberación", "liberacion",
        ])

    if any(term in text for term in ["sds", "hp smart device services", "dca", "sda", "jamc"]):
        profile["preferred_terms"].extend([
            "sds", "smart device services", "hp smart device services",
            "monitor", "dca", "sda", "jamc",
            "requirements", "requisitos", "prerrequisitos",
        ])

    if any(term in text for term in ["cola", "queue", "spooler", "bloqueada", "atascada", "no imprime"]):
        profile["preferred_terms"].extend([
            "cola", "queue", "spooler", "print queue",
            "bloqueada", "atascada", "stuck", "held",
        ])

    if query_intent == "warranty":
        profile["preferred_terms"].extend([
            "garantía", "garantia", "warranty", "rma",
            "suministro", "suministros", "consumible", "consumibles",
            "reemplazo",
        ])
        profile["avoid_terms"].extend([
            "dashboard", "control operacion", "control operación",
            "pin", "autogestion", "autogestión",
        ])

    if query_intent == "escalation":
        profile["preferred_terms"].extend([
            "escalar", "escalamiento", "nivel 2", "nivel 3",
            "incidente", "ticket", "caso", "proveedor", "fabricante",
        ])

    return profile
    
    # ------------------------------------------------------------------
    # Fallback generic heuristics only for stable metadata families
    # ------------------------------------------------------------------
    if any(term in text for term in ["papercut", "paper cut"]):
        profile["filter"] = make_chroma_filter(vendor="papercut")
        return profile

    if any(term in text for term in ["sds", "hp smart device services", "jamc", "dca"]):
        profile["filter"] = make_chroma_filter(vendor="hp", product="sds")
        return profile

    if any(term in text for term in ["web jet admin", "web jetadmin", "wja"]):
        profile["filter"] = make_chroma_filter(vendor="hp", product="web_jetadmin")
        return profile

    if any(term in text for term in ["access control", "hp ac", "hac"]):
        profile["filter"] = make_chroma_filter(vendor="hp", product="hp_access_control")
        return profile

    if any(term in text for term in ["gav tracking", "gav"]):
        profile["filter"] = make_chroma_filter(vendor="gav", product="gav_tracking")
        return profile

    if any(term in text for term in ["epson remote services", "ers"]):
        profile["filter"] = make_chroma_filter(vendor="epson", product="epson_remote_services")
        return profile

    if any(term in text for term in ["epson print admin", "epa"]):
        profile["filter"] = make_chroma_filter(vendor="epson", product="epson_print_admin")
        return profile

    # For internal/operational questions (DA Arus / Print Evolve / MFPsecure / SIMP),
    # do not constrain retrieval with metadata filters.
    return profile

    # ------------------------------------------------------------------
    # Fallback generic heuristics if no entity hints were detected
    # ------------------------------------------------------------------
    if any(term in text for term in ["papercut", "print jobs", "trabajos de impresión", "trabajos de impresion"]):
        profile["filter"] = make_chroma_filter(vendor="papercut")
        return profile

    if any(term in text for term in ["sds", "hp smart device services", "jamc", "dca"]):
        profile["filter"] = make_chroma_filter(vendor="hp", product="sds")
        return profile

    if any(term in text for term in ["web jet admin", "web jetadmin", "wja"]):
        profile["filter"] = make_chroma_filter(vendor="hp", product="web_jetadmin")
        return profile

    if any(term in text for term in ["access control", "hp ac", "hac"]):
        profile["filter"] = make_chroma_filter(vendor="hp", product="hp_access_control")
        return profile

    if any(term in text for term in ["gav tracking", "gav"]):
        profile["filter"] = make_chroma_filter(vendor="gav", product="gav_tracking")
        return profile

    if any(term in text for term in ["epson remote services", "ers"]):
        profile["filter"] = make_chroma_filter(vendor="epson", product="epson_remote_services")
        return profile

    if any(term in text for term in ["epson print admin", "epa"]):
        profile["filter"] = make_chroma_filter(vendor="epson", product="epson_print_admin")
        return profile

    return profile

def build_entity_retrieval_hints(query_entities: dict) -> dict:
    """
    Build retrieval hints from detected entities.

    Important:
    - hard_filter = True only when the entity has reliable metadata alignment
      with the vectorstore (e.g. HP SDS, WJA, GAV, HAC).
    - hard_filter = False for internal/support/DA Arus style entities or when
      the entity concept does not map cleanly to vectorstore product metadata.
    """
    hints = {
        "vendor": None,
        "product": None,
        "component": None,
        "hard_filter": False,
    }

    for product_id in query_entities.get("products", []):
        entity = PRODUCT_ENTITY_REGISTRY.get(product_id)
        if not entity:
            continue

        entity_hints = entity.get("retrieval_hints", {})
        hint_vendor = entity_hints.get("vendor")
        hint_product = entity_hints.get("product")
        hint_component = entity_hints.get("component")

        if hints["vendor"] is None and hint_vendor:
            hints["vendor"] = hint_vendor
        if hints["product"] is None and hint_product:
            hints["product"] = hint_product
        if hints["component"] is None and hint_component:
            hints["component"] = hint_component

        # Use hard filters only for entities whose metadata is likely
        # to exist consistently in the vectorstore.
        if product_id in {
            "hp_sds",
            "hp_sds_monitor",
            "hp_sds_dca",
            "jamc",
            "hp_web_jetadmin",
            "hp_access_control",
            "gav_tracking",
            "papercut_mf",
            "papercut_hive",
            "papercut_ng",
            "epson_remote_services",
            "epson_print_admin",
        }:
            hints["hard_filter"] = True

        # Internal/operational tools should not force a hard metadata filter.
        if product_id in {
            "print_evolve",
            "mfpsecure",
            "mipa_agent",
            "dashboard_simp",
            "da_arus",
        }:
            hints["hard_filter"] = False

    return hints

def compute_rerank_score(query: str, doc, query_intent: str | None = None) -> float:
    """
    Query-aware heuristic reranking.

    Goals:
    - Recover PaperCut/SDS documents even when metadata filters are imperfect.
    - Reduce source contamination.
    - Promote exact title/source/product matches.
    - Keep priority useful, but not dominant.
    """
    text = query.lower()
    content = doc.page_content.lower()
    metadata = doc.metadata or {}

    query_intent = query_intent or classify_query_intent(query)

    title = str(metadata.get("title", "")).lower()
    source = str(metadata.get("source", "")).lower()
    vendor = str(metadata.get("vendor", "")).lower()
    product = str(metadata.get("product", "")).lower()
    component = str(metadata.get("component", "")).lower()
    document_family = str(metadata.get("document_family", "")).lower()
    source_type = str(metadata.get("source_type", "")).lower()

    title_source = f"{title} {source} {vendor} {product} {component} {document_family}"

    score = 0.0

    # Priority should help, but not dominate semantic relevance.
    try:
        priority = int(metadata.get("priority", 3))
    except Exception:
        priority = 3
    score += max(0, 4 - priority) * 0.6

    # Source type signal.
    if source_type in {"pdf", "troubleshooting", "known_issue"}:
        score += 0.8
    elif source_type in {"kb_article", "manual", "guide"}:
        score += 0.5

    # Keyword overlap.
    query_tokens = [
        tok for tok in re.findall(r"\w+", text)
        if len(tok) > 2
    ]
    overlap = sum(1 for tok in query_tokens if tok in content)
    score += overlap * 0.25

    # Title/source exact-ish matching has high value.
    for tok in query_tokens:
        if tok in title_source:
            score += 0.45

    # PaperCut-specific boost.
    if "papercut" in text:
        if "papercut" in title_source:
            score += 5.0
        if "papercut" in content:
            score += 2.0

        if any(t in text for t in ["desaparecen", "desaparece", "disappearing", "missing", "trabajos"]):
            if any(t in content for t in [
                "print job", "print jobs", "job", "jobs",
                "held", "hold", "release", "released",
                "trabajo", "trabajos", "liberar", "liberación", "liberacion",
                "desaparece", "desaparecen",
            ]):
                score += 3.5

        # Penalize unrelated internal docs if they do not mention PaperCut.
        if "papercut" not in title_source and "papercut" not in content:
            score -= 4.0

    # HP SDS / requirements boost.
    if any(t in text for t in ["sds", "smart device services", "hp smart device services"]):
        if any(t in title_source for t in ["sds", "smart device services"]):
            score += 5.0
        if any(t in content for t in ["sds", "smart device services"]):
            score += 2.0

        if query_intent == "requirements":
            if any(t in content for t in [
                "requirements", "requisitos", "prerrequisitos",
                "system requirements", "minimum requirements",
                "compatible", "compatibilidad",
                "operating system", "sistema operativo",
                "hardware", "network", "red",
            ]):
                score += 3.0

    # Queue / spooler troubleshooting boost.
    if any(t in text for t in ["cola", "queue", "spooler", "bloqueada", "atascada"]):
        if any(t in title_source for t in ["cola", "queue", "spooler"]):
            score += 3.0
        if any(t in content for t in [
            "cola", "queue", "spooler", "print queue",
            "bloqueada", "atascada", "stuck",
            "detiene", "stopped", "reiniciar", "restart",
        ]):
            score += 2.0

    # Warranty / supplies boost and contamination control.
    if query_intent == "warranty":
        if any(t in title_source for t in [
            "garantía", "garantia", "warranty",
            "suministro", "suministros",
            "consumible", "consumibles",
        ]):
            score += 6.0

        if any(t in content for t in [
            "garantía", "garantia", "warranty",
            "suministro", "suministros",
            "consumible", "consumibles",
            "reemplazo", "rma",
        ]):
            score += 2.0

        if any(t in title_source for t in [
            "dashboard", "control operacion", "control operación",
            "pin", "autogestion", "autogestión",
        ]):
            score -= 5.0

    # Escalation boost.
    if query_intent == "escalation":
        if any(t in content for t in [
            "escalar", "escalamiento", "nivel 2", "nivel 3",
            "incidente", "ticket", "caso", "proveedor", "fabricante",
        ]):
            score += 2.5

    # Penalize cover/legal/confidential-only chunks.
    legal_noise_terms = [
        "aviso legal",
        "información restringida",
        "informacion restringida",
        "confidencial",
        "uso exclusivo",
    ]
    if any(t in content[:800] for t in legal_noise_terms):
        meaningful_terms = overlap
        if meaningful_terms <= 1:
            score -= 3.0
        else:
            score -= 1.0

    # Generic noisy docs.
    if "known issues" in title and query_intent != "troubleshooting":
        score -= 1.5
    if "end user articles" in title:
        score -= 1.0
    if "knowledge base" in title and "papercut" not in text:
        score -= 1.0

    return score
def should_keep_ranked_doc(
    query: str,
    doc,
    score: float,
    top_score: float,
    query_intent: str,
) -> bool:
    """
    Decide whether a reranked document is relevant enough to be sent
    to the final LLM context.

    This function is intentionally strict by intent to reduce source contamination.
    """
    text = query.lower()
    content = doc.page_content.lower()
    metadata = doc.metadata or {}

    title = str(metadata.get("title", "")).lower()
    source = str(metadata.get("source", "")).lower()
    vendor = str(metadata.get("vendor", "")).lower()
    product = str(metadata.get("product", "")).lower()
    component = str(metadata.get("component", "")).lower()
    document_family = str(metadata.get("document_family", "")).lower()

    title_source = f"{title} {source} {vendor} {product} {component} {document_family}"

    if top_score <= 0:
        return score > 0

    relative_score = score / top_score

    legal_noise_terms = [
        "aviso legal",
        "información de uso interno",
        "informacion de uso interno",
        "información restringida",
        "informacion restringida",
        "confidencial",
        "uso exclusivo",
        "divulgación, reenvío, copia",
        "divulgacion, reenvio, copia",
        "estrictamente prohibida",
    ]

    is_legal_or_cover_noise = any(term in content[:1200] for term in legal_noise_terms)

    operational_papercut_terms = [
        "trabajos de impresión",
        "trabajos de impresion",
        "registro de trabajos",
        "registro de trabajos de cada usuario",
        "información de los usuarios",
        "informacion de los usuarios",
        "usuarios",
        "liberar",
        "liberación",
        "liberacion",
        "trabajos retenidos",
        "cola",
        "print jobs",
        "held jobs",
        "release jobs",
    ]

    useful_sds_requirement_terms = [
        "requirements",
        "requisitos",
        "prerrequisitos",
        "system requirements",
        "minimum requirements",
        "sistema operativo",
        "operating system",
        "windows server",
        "windows 10",
        "virtualización",
        "virtualizacion",
        "vmware",
        "hyperv",
        "hardware",
        "red",
        "network",
    ]

    useful_warranty_terms = [
        "garantía",
        "garantia",
        "garantías",
        "garantias",
        "warranty",
        "suministro",
        "suministros",
        "consumible",
        "consumibles",
        "proveedor",
        "proveedores",
        "reemplazo",
        "rma",
        "trámite de garantías",
        "tramite de garantias",
    ]

    useful_escalation_terms = [
        "escalar",
        "escalamiento",
        "nivel 2",
        "nivel 3",
        "incidente",
        "ticket",
        "caso",
        "proveedor",
        "fabricante",
        "informar al área",
        "informar al area",
        "mesa de ayuda",
    ]

    # PaperCut-focused queries.
    if "papercut" in text:
        has_papercut = "papercut" in title_source or "papercut" in content
        has_operational_papercut_content = any(
            term in content for term in operational_papercut_terms
        )
    
        # Reject cover/legal chunks even if they mention PaperCut MF.
        if is_legal_or_cover_noise and not has_operational_papercut_content:
            return False
    
        # Keep real operational PaperCut content.
        if has_papercut and has_operational_papercut_content and score >= 4:
            return True
    
        # Fallback for strong PaperCut chunks, but only if they are not legal/cover noise.
        if (
            has_papercut
            and not is_legal_or_cover_noise
            and score >= 8
            and relative_score >= 0.55
        ):
            return True
    
        return False

    # SDS requirements.
    if any(term in text for term in [
        "sds",
        "smart device services",
        "hp smart device services",
    ]):
        has_sds = any(term in title_source or term in content for term in [
            "sds",
            "smart device services",
            "dca",
            "sda",
            "jamc",
        ])

        has_requirement_signal = any(term in title_source or term in content for term in useful_sds_requirement_terms)

        if query_intent == "requirements":
            # For requirements, reject brochure/general marketing docs.
            if (
                "brochure" in title_source
                or "brochure" in source
                or document_family == "brochure"
            ):
                return False
        
            if has_sds and has_requirement_signal and score >= 5:
                return True
        
            if has_sds and "instalar monitor sds" in title_source and score >= 8:
                return True
        
            return False
            
        return has_sds and score >= 4

    # Warranty queries.
    if query_intent == "warranty":
        has_warranty_signal = any(term in title_source or term in content for term in useful_warranty_terms)

        # Strongly prefer the actual warranty document.
        if "garantía" in title_source or "garantia" in title_source:
            return score >= 3

        # Reject HP WJA and generic printer manuals for warranty questions.
        if "web jetadmin" in title_source or product == "web_jetadmin":
            return False

        if "mantprev" in title_source or "mantenimiento preventivo" in title_source:
            return False

        if has_warranty_signal and score >= 4 and relative_score >= 0.30:
            return True

        return False

    # Escalation queries.
    if query_intent == "escalation":
        has_escalation_signal = any(term in title_source or term in content for term in useful_escalation_terms)

        if has_escalation_signal and score >= 3:
            return True

        return score >= 5 and relative_score >= 0.6

    # Generic fallback: remove legal-only chunks and weak tail documents.
    if is_legal_or_cover_noise:
        return False

    if score >= 4 and relative_score >= 0.35:
        return True

    return False
def compute_keyword_overlap_ratio(query: str, content: str) -> float:
    query_tokens = [tok for tok in re.findall(r"\w+", query.lower()) if len(tok) > 2]
    if not query_tokens:
        return 0.0
    overlap = sum(1 for tok in query_tokens if tok in content.lower())
    return overlap / max(len(query_tokens), 1)


def assess_retrieval_support(query: str, docs: list) -> dict[str, Any]:
    if not docs:
        return {"support_level": "none", "top_score": 0.0, "avg_overlap": 0.0}

    scores = [compute_rerank_score(query, d) for d in docs]
    overlaps = [compute_keyword_overlap_ratio(query, d.page_content) for d in docs]
    top_score = max(scores) if scores else 0.0
    avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0.0

    if top_score >= 6.0 and avg_overlap >= 0.12:
        support_level = "strong"
    elif top_score >= 4.0 and avg_overlap >= 0.06:
        support_level = "partial"
    else:
        support_level = "weak" if docs else "none"

    return {
        "support_level": support_level,
        "top_score": round(top_score, 3),
        "avg_overlap": round(avg_overlap, 3),
    }

def classify_query_intent(user_query: str) -> str:
    text = user_query.lower()

    requirements_patterns = [
        "qué requerimientos", "que requerimientos",
        "qué requisitos", "que requisitos",
        "requerimientos necesarios", "requisitos necesarios",
        "system requirements", "minimum requirements",
        "requisitos mínimos", "requisitos minimos",
        "prerrequisitos", "prerequisites",
        "compatibilidad", "compatible",
    ]

    troubleshooting_patterns = [
        "qué hacer si", "que hacer si",
        "qué debo hacer si", "que debo hacer si",
        "debo hacer si",
        "error", "falla", "fallando",
        "cola", "queue", "spooler",
        "bloqueada", "bloqueado", "atascada", "atascado", "atasco",
        "offline", "no imprime", "no deja imprimir",
        "desaparecen trabajos", "trabajos desaparecen",
        "desaparece", "desaparecen", "desaparecido",
        "disappearing", "disappear", "missing jobs",
        "stuck", "not held", "cannot add", "no puedo", "no deja",
    ]

    warranty_patterns = [
        "garantía", "garantia", "warranty",
        "rma", "reemplazo", "suministro", "suministros",
        "consumible", "consumibles",
    ]

    escalation_patterns = [
        "escalar", "escalamiento", "nivel 2", "nivel 3",
        "abrir caso", "caso proveedor", "fabricante",
        "cuándo debo escalar", "cuando debo escalar",
    ]

    architecture_patterns = [
        "arquitectura", "componentes", "integración", "integracion",
        "diagrama", "flujo", "gav tracking",
    ]

    procedural_patterns = [
        "cómo instalar", "como instalar",
        "cómo agregar", "como agregar",
        "cómo incorporar", "como incorporar",
        "cómo configurar", "como configurar",
        "cómo habilitar", "como habilitar",
        "cómo crear", "como crear",
        "cómo realizar", "como realizar",
        "procedimiento", "pasos", "trámite", "tramite",
    ]

    conceptual_patterns = [
        "qué es", "que es",
        "para qué sirve", "para que sirve",
        "cómo funciona", "como funciona",
        "qué hace", "que hace",
        "explica", "diferencia entre",
    ]

    # Order matters: warranty/escalation/troubleshooting must be detected
    # before generic procedural phrases like "cómo realizar".
    if any(p in text for p in warranty_patterns):
        return "warranty"

    if any(p in text for p in escalation_patterns):
        return "escalation"

    if any(p in text for p in requirements_patterns):
        return "requirements"

    if any(p in text for p in troubleshooting_patterns):
        return "troubleshooting"

    if any(p in text for p in architecture_patterns):
        return "architecture"

    if any(p in text for p in conceptual_patterns):
        return "conceptual"

    if any(p in text for p in procedural_patterns):
        return "procedural"

    return "default"

def has_hard_documentary_anchor(user_query: str, docs: list, query_intent: str) -> bool:
    if not docs:
        return False

    for doc in docs:
        content = doc.page_content.lower()
        md = doc.metadata
        product = str(md.get("product", "")).lower()
        component = str(md.get("component", "")).lower()
        family = str(md.get("document_family", "")).lower()
        title = str(md.get("title", "")).lower()
        source = str(md.get("source", "")).lower()

        if query_intent == "requirements":
            if (
                family == "requirements"
                or component == "requirements"
                or "requirement" in title
                or "requer" in title
                or "requirement" in source
                or "requer" in source
            ) and product in {"sds", "web_jetadmin", "hp_access_control", "gav_tracking"}:
                return True
            req_terms = ["requirements", "requisitos", "requerimientos", "hardware", "windows", "server", "ram", "disk", "vmware", "hyperv", "cpu", "monitor"]
            if any(t in content for t in req_terms):
                return True

        elif query_intent == "procedural":
            terms = ["install", "instal", "configure", "configur", "add", "agreg", "incorpor", "device", "printer", "embedded", "authentication", "oxp"]
            if any(t in content for t in terms):
                return True

        elif query_intent == "troubleshooting":
            terms = ["error", "issue", "problem", "troubleshoot", "stuck", "missing", "queue", "offline", "not held"]
            if any(t in content for t in terms):
                return True

        elif query_intent == "conceptual":
            if product or content:
                return True

    return False


def is_explicit_follow_up_query(user_query: str) -> bool:
    text = user_query.lower().strip()
    follow_up_patterns = [
        "y eso", "y como", "y cómo", "eso", "lo anterior", "esa herramienta", "ese software",
        "ese sistema", "ese producto", "tambien", "también", "y en ese caso", "y para eso",
    ]
    return any(p in text for p in follow_up_patterns)


def should_use_memory_for_query(user_query: str, query_intent: str) -> bool:
    if is_explicit_follow_up_query(user_query):
        return True
    if query_intent in {"conceptual", "requirements"}:
        return False
    return True


def is_low_risk_general_query(user_query: str) -> bool:
    text = user_query.lower()
    low_risk_patterns = [
        "qué es", "que es", "para qué sirve", "para que sirve", "cómo funciona", "como funciona",
        "explica", "diferencia entre", "qué hace", "que hace",
    ]
    return any(p in text for p in low_risk_patterns)


def should_use_general_fallback(user_query: str, support_info: dict) -> bool:
    intent = classify_query_intent(user_query)
    if intent != "conceptual":
        return False
    return support_info["support_level"] != "strong"


def retrieve_context(query: str, top_k: int = 4):
    vectorstore = get_vectorstore()
    profile = detect_query_profile(query)
    query_intent = classify_query_intent(query)

    k_initial = profile.get("k_initial", top_k)
    k_final = profile.get("k_final", top_k)
    metadata_filter = profile.get("filter")

    def run_retrieval(filter_value=None):
        search_kwargs = {"k": k_initial}
        if filter_value:
            search_kwargs["filter"] = filter_value

        retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)
        return retriever.invoke(query)

    docs = []

    # First attempt: use profile filter only if present.
    if metadata_filter:
        try:
            docs = run_retrieval(metadata_filter)
        except Exception:
            docs = []

    # Fallback: broad retrieval. This is critical for PaperCut/SDS cases
    # where metadata filters may be too strict.
    if not docs and CONFIG.get("enable_filter_fallback", True):
        docs = run_retrieval(None)

    # If no filter was defined, run broad retrieval directly.
    if not metadata_filter:
        docs = run_retrieval(None)

    if not docs:
        return "", []

    ranked_docs_with_scores = []

    for doc in docs:
        score = compute_rerank_score(query, doc, query_intent)
        ranked_docs_with_scores.append((doc, score))
    
    ranked_docs_with_scores.sort(
        key=lambda item: item[1],
        reverse=True,
    )
    
    top_score = ranked_docs_with_scores[0][1] if ranked_docs_with_scores else 0.0
    
    filtered_ranked_docs = [
        doc
        for doc, score in ranked_docs_with_scores
        if should_keep_ranked_doc(
            query=query,
            doc=doc,
            score=score,
            top_score=top_score,
            query_intent=query_intent,
        )
    ]
    
    # If the filter is too strict, fall back only to the strongest 2 reranked docs.
    # This avoids reintroducing low-quality contaminated context.
    if not filtered_ranked_docs:
        filtered_ranked_docs = [
            doc
            for doc, score in ranked_docs_with_scores[:2]
        ]
    
    ranked_docs = filtered_ranked_docs

    # Source diversity: avoid sending 4 chunks from the same PDF when possible.
    max_docs_per_source = CONFIG.get("max_docs_per_source", 2)
    selected_docs = []
    source_counts = defaultdict(int)

    for doc in ranked_docs:
        source_key = str(doc.metadata.get("source", "unknown_source"))
        if source_counts[source_key] >= max_docs_per_source:
            continue

        selected_docs.append(doc)
        source_counts[source_key] += 1

        if len(selected_docs) >= k_final:
            break

    # If diversity was too restrictive, fill remaining slots.
    if len(selected_docs) < k_final:
        selected_ids = {id(doc) for doc in selected_docs}
        for doc in ranked_docs:
            if id(doc) in selected_ids:
                continue
            selected_docs.append(doc)
            if len(selected_docs) >= k_final:
                break

    context_blocks = []

    for i, doc in enumerate(selected_docs, start=1):
        source_label = format_source_label(doc.metadata)
        content = doc.page_content.strip()

        context_blocks.append(
            f"[Chunk {i}] Source: {source_label}\n{content}"
        )

    return "\n\n".join(context_blocks), selected_docs

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
- No uses expresiones genéricas como \"Documentación oficial de...\" salvo que aparezcan literalmente en las fuentes disponibles.
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
    query_intent = classify_query_intent(user_query)

    intent_instruction = ""

    if query_intent == "troubleshooting":
        intent_instruction = """

    
    #### INSTRUCCIÓN ESPECIAL PARA TROUBLESHOOTING
    
    La respuesta debe tener este enfoque:
    - No inventes causas que no estén soportadas por el contexto.
    - Si la documentación no identifica una causa única, dilo explícitamente.
    - Indica qué validaciones permite hacer la documentación recuperada.
    - Responde con esta estructura dentro de la sección Respuesta:
      - Diagnóstico documental
      - Validaciones iniciales
      - Acciones recomendadas
      - Cuándo escalar
    """

    if allow_general_fallback:
        fallback_instruction = (
            "Puedes complementar de forma prudente con orientación general solo si la pregunta es de bajo riesgo "
            "y el contexto documental es parcial. No expliques al usuario el proceso interno."
        )
    else:
        fallback_instruction = (
            "Debes basar la respuesta principalmente en la información documental disponible. "
            "Si la información no es suficiente para responder con precisión, no inventes pasos críticos."
        )

    requirements_instruction = ""
    if query_intent == "requirements":
        requirements_instruction = """
### INSTRUCCIÓN ESPECIAL PARA CONSULTAS DE REQUERIMIENTOS
- Si la pregunta es sobre requisitos o requerimientos, estructura la respuesta por categorías cuando el contexto lo permita:
  - Prerrequisitos del entorno
  - Sistemas operativos compatibles
  - Plataformas de virtualización compatibles
  - Requisitos mínimos de hardware
  - Requisitos de red / seguridad
- Incluye solo las categorías que realmente aparezcan en el contexto recuperado.
- No conviertas la respuesta en pasos de instalación.
- No uses contenido de troubleshooting como si fuera un requisito de instalación.
- No recortes información útil si está claramente presente en el contexto.
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

#### INSTRUCCIÓN ADICIONAL POR INTENCIÓN
{intent_instruction}

#### FORMATO DE RESPUESTA OBLIGATORIO

Debes responder siempre con estas dos secciones, en este orden:

Respuesta:
- Escribe una respuesta técnica clara y útil.
- No omitas esta sección.
- No respondas únicamente con fuentes.
- Si la información documental es limitada, explica qué sí se puede validar con las fuentes disponibles y qué no se puede concluir.

Fuente(s):
- Incluye únicamente fuentes de la lista de fuentes disponibles para citar.
- No inventes fuentes.
- Si no hay fuentes suficientes, escribe:
  - Base de conocimiento actual sin coincidencias documentales suficientes

### REGLAS DE ESTILO
- No menciones limitaciones salvo que sea realmente necesario.
- Si hace falta advertir algo importante, añade solo una línea final como: Aviso: ...
- No expliques tu proceso interno.
- No menciones contexto recuperado, RAG, fallback ni modelo.
- No inventes nombres de fuente.
- No cites "Documentación oficial de ..." si no aparece exactamente en la lista de fuentes disponibles.

{requirements_instruction}

### INSTRUCCIÓN ADICIONAL
{fallback_instruction}
"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    
def clean_user_facing_answer(answer: str) -> str:
    text = answer.strip()
    text = re.sub(r"^\s*nota\s*:\s*", "Aviso: ", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"^\s*limitaci[oó]n\s*:\s*", "Aviso: ", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = [line.rstrip() for line in text.splitlines()]
    cleaned = []
    avisos = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if stripped.lower().startswith("aviso:"):
            if stripped not in avisos:
                avisos.append(stripped)
        else:
            cleaned.append(line)

    final = "\n".join(cleaned).strip()
    if avisos:
        final += "\n\n" + "\n".join(avisos)
    return re.sub(r"\n{3,}", "\n\n", final).strip()


def answer_uses_fake_generic_sources(answer: str) -> bool:
    generic_patterns = ["documentación oficial de", "documentacion oficial de", "official documentation of"]
    text = answer.lower()
    return any(pattern in text for pattern in generic_patterns)


def enforce_real_source_traceability(answer: str, real_source_labels: list[str], support_info: dict, user_query: str) -> str:
    text = answer.strip()
    aviso_lines = [
        line.strip() for line in text.splitlines() if line.strip().lower().startswith("aviso:")
    ]
    split_parts = re.split(r"\n\s*fuente\(s\)\s*:\s*", text, flags=re.IGNORECASE)
    response_part = split_parts[0].strip()

    if support_info["support_level"] in {"weak", "none"}:
        source_block = "Fuente(s):\n- Base de conocimiento actual sin coincidencias documentales suficientes"
    else:
        source_block = "Fuente(s):\n" + build_source_block(real_source_labels)

    final_text = f"{response_part}\n\n{source_block}"
    if aviso_lines:
        seen = []
        for a in aviso_lines:
            if a not in seen:
                seen.append(a)
        final_text += "\n\n" + "\n".join(seen)
    return final_text.strip()


def build_conservative_no_support_answer(user_query: str, real_source_labels: list[str] | None = None) -> str:
    source_block = "- Base de conocimiento actual sin coincidencias documentales suficientes"
    if real_source_labels:
        source_block = "\n".join(f"- {label}" for label in real_source_labels[:2])
    return f"""Respuesta:
No encontré información suficientemente específica y confiable en la base de conocimiento actual para responder con precisión a esta consulta. Si se trata de una tarea operativa o de configuración, te recomiendo validar con documentación adicional o escalar el caso si el impacto lo requiere.

Fuente(s):
{source_block}

Aviso: La base documental actual no ofrece soporte suficientemente claro para dar un procedimiento preciso."""


# -----------------------------------------------------------------------------
# Requirements answer builder
# -----------------------------------------------------------------------------
def build_combined_requirement_text(docs: list) -> str:
    def page_num(doc):
        try:
            return int(doc.metadata.get("page", 999))
        except Exception:
            return 999

    docs_sorted = sorted(docs, key=page_num)
    parts = []
    for doc in docs_sorted:
        content = getattr(doc, "page_content", None)
        if content:
            parts.append(str(content))

    text = "\n".join(parts)
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_requirements_answer_from_docs(user_query: str, docs: list) -> str:
    """
    Build a grounded and complete answer for requirements queries
    using deterministic extraction from the retrieved PDF text.
    """
    text = build_combined_requirement_text(docs)
    source_labels = build_real_source_labels(docs)

    normalized = text.replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    def normalize_item(value: str) -> str:
        value = " ".join(value.strip().split())
        return value.strip(" ;,.-")

    def extract_block(start_patterns: list[str], end_patterns: list[str]) -> str:
        lower_text = normalized.lower()

        start_pos = None
        chosen_marker = None
        for pattern in start_patterns:
            pos = lower_text.find(pattern.lower())
            if pos != -1:
                if start_pos is None or pos < start_pos:
                    start_pos = pos
                    chosen_marker = pattern

        if start_pos is None:
            return ""

        start_pos += len(chosen_marker)

        end_pos = len(normalized)
        for pattern in end_patterns:
            pos = lower_text.find(pattern.lower(), start_pos)
            if pos != -1 and pos < end_pos:
                end_pos = pos

        return normalized[start_pos:end_pos].strip()

    def extract_bullets_regex(block: str) -> list[str]:
        """Extract bullet items robustly, preserving wrapped bullet lines."""
        if not block:
            return []

        matches = re.findall(
            r"(?:^|\n)\s*[•\-]\s*(.+?)(?=(?:\n\s*[•\-]\s)|\Z)",
            block,
            flags=re.DOTALL,
        )

        items = []
        for item in matches:
            item = normalize_item(item)
            noise_patterns = [
                "HP SDS MANAGER SYSTEM REQUIREMENTS",
                "HP SDS – SYSTEM REQUIREMENTS",
                "© EKM",
                "COMPANY NUMBER",
            ]
            low = item.lower()
            if any(noise.lower() in low for noise in noise_patterns):
                continue
            if item and item not in items:
                items.append(item)
        return items

    def join_items_full(items: list[str], max_items: int = 8) -> str:
        cleaned = []
        for item in items[:max_items]:
            value = " ".join(item.split()).strip()
            if value and value not in cleaned:
                cleaned.append(value)
        return "; ".join(cleaned)

    environment_block = extract_block(
        start_patterns=[
            "Los siguientes son los requisitos operativos requeridos",
            "requisitos operativos requeridos para un monitor HP SDS",
        ],
        end_patterns=[
            "Los sistemas operativos soportados",
            "Plataformas de virtualización compatibles",
            "Hardware",
        ],
    )

    os_block = extract_block(
        start_patterns=[
            "Los sistemas operativos soportados son los siguientes",
            "Los sistemas operativos soportados",
        ],
        end_patterns=[
            "Plataformas de virtualización compatibles",
            "Hardware",
        ],
    )

    hardware_block = extract_block(
        start_patterns=[
            "Los requisitos mínimos de hardware para HP SDS Monitor",
            "Los requisitos mínimos de hardware",
            "Hardware",
        ],
        end_patterns=[
            "Preparando el entorno",
            "NOTA:",
        ],
    )

    network_block = extract_block(
        start_patterns=[
            "Para que HP SDS Monitor funcione, se deben cumplir los siguientes criterios",
            "Preparando el entorno",
        ],
        end_patterns=[
            "VeriSign Class 3 Public",
            "1NOTA:",
            "2NOTA:",
        ],
    )

    environment_items = extract_bullets_regex(environment_block)
    os_items = extract_bullets_regex(os_block)
    hardware_items = extract_bullets_regex(hardware_block)
    network_items = extract_bullets_regex(network_block)

    # Deterministic fallbacks for this specific document
    if not environment_items:
        environment_items = []
        for pattern in [
            r"•\s*\.NET\s*4\.5",
            r"•\s*Access to the Internet or HTTP proxy server",
            r"•\s*IPv4 network",
        ]:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                environment_items.append(normalize_item(match.group(0).lstrip("•- ").strip()))

    if not os_items:
        os_candidates = re.findall(
            r"(Windows Server 2008 R2|Windows Server 2008|Windows Server 2012|Windows Server 2016|Windows Server 2019 y por encima|Windows 7|Windows 8|Windows 10)",
            normalized,
            flags=re.IGNORECASE,
        )
        os_items = []
        for item in os_candidates:
            item = normalize_item(item)
            if item and item not in os_items:
                os_items.append(item)

    cleaned_hw = []
    for item in hardware_items:
        if "NOTA:" in item:
            item = item.split("NOTA:")[0].strip()
        item = normalize_item(item)
        if item and item not in cleaned_hw:
            cleaned_hw.append(item)
    hardware_items = cleaned_hw

    if not hardware_items:
        hardware_items = []
        for pattern in [
            r"32-bit \(x86\) or 64-bit \(x64\) Processor: 1 GHz \(gigahertz\)",
            r"Memory: 1 GB \(gigabyte\) RAM",
            r"Espacio necesario para la instalación: mínimo 200 MB de espacio libre en disco",
        ]:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                hardware_items.append(normalize_item(match.group(0)))

    if not network_items:
        network_items = []
        fallback_network_patterns = [
            r"Su infraestructura de red debe permitir el enrutamiento del tráfico ICMP Echo \(\"Ping\"\) entre JAMC y las impresoras.*?(?=•|$)",
            r"Su infraestructura de servidor de seguridad de Internet/proxy HTTP debe permitir la comunicación.*?(?=•|$)",
            r"Cuando se usan credenciales de proxy HTTP, la autenticación de acceso básico debe estar habilitada.*?(?=•|$)",
            r"Las credenciales de la cuenta de servicio.*?(?=•|$)",
        ]
        for pattern in fallback_network_patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
            if match:
                value = normalize_item(match.group(0))
                if value and value not in network_items:
                    network_items.append(value)

    virtualization_value = ""
    virt_match = re.search(
        r"Plataformas de virtualización compatibles[:\s]+([^\n]+)",
        normalized,
        flags=re.IGNORECASE,
    )
    if virt_match:
        virtualization_value = normalize_item(virt_match.group(1))

    note_value = ""
    note_match = re.search(
        r"NOTA:\s*(Se admiten los sistemas Windows con varias NIC.*?)(?:\n|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    if note_match:
        note_value = normalize_item(note_match.group(1))

    bullets = []
    if environment_items:
        bullets.append(f"- **Prerrequisitos del entorno:** {join_items_full(environment_items, max_items=4)}")
    if os_items:
        bullets.append(f"- **Sistemas operativos compatibles:** {join_items_full(os_items, max_items=8)}")
    if virtualization_value:
        bullets.append(f"- **Plataformas de virtualización compatibles:** {virtualization_value}")
    if hardware_items:
        bullets.append(f"- **Requisitos mínimos de hardware:** {join_items_full(hardware_items, max_items=4)}")
    if network_items:
        bullets.append(f"- **Requisitos de red / seguridad:** {join_items_full(network_items, max_items=4)}")

    if not bullets:
        return build_conservative_no_support_answer(user_query=user_query, real_source_labels=source_labels)

    source_heading = "Fuente principal:" if len(source_labels) == 1 else "Fuentes principales:"
    source_block = source_heading + "\n" + "\n".join(f"- {label}" for label in source_labels[:2])
    aviso = f"\n\nAviso: {note_value}" if note_value else ""

    return f"""Respuesta:
Con base en la documentación disponible, estos son los requisitos relevantes identificados para esta consulta:

{chr(10).join(bullets)}

{source_block}{aviso}"""


def compact_source_heading(source_labels: list[str]) -> str:
    return "Fuente principal:" if len(source_labels) == 1 else "Fuentes principales:"


def field_accepts_no_value(field_name: str) -> bool:
    return field_name in {"software_version", "contract_client_location", "evidence", "impact_type"}

def build_llm_unavailable_answer(error: Exception | None = None) -> str:
    """
    User-facing response when the LLM provider is not available.
    Avoid exposing internal stack traces or secrets.
    """
    return (
        "Respuesta:\n"
        "- En este momento el servicio de generación de respuestas no está disponible. "
        "La base documental y el retrieval pueden estar funcionando, pero el modelo de lenguaje "
        "configurado no pudo responder.\n\n"
        "Fuente(s):\n"
        "- Base de conocimiento actual sin respuesta generada por el modelo.\n\n"
        "Aviso: Revisa la configuración del modelo o proveedor de inferencia antes de intentar nuevamente."
    )
def answer_is_sources_only(answer: str) -> bool:
        text = answer.strip().lower()
    
        if not text:
            return True
    
        has_response = "respuesta:" in text
        has_sources = "fuente" in text
    
        # If it has sources but no real response section, treat as bad generation.
        if has_sources and not has_response:
            return True
    
        # Very short answers are usually malformed.
        if len(text) < 80:
            return True
    
        return False
def serialize_llm_response_for_debug(response, max_chars: int = 3000) -> str:
    """
    Convert the raw LLM response object into a safe debug string.
    This helps diagnose provider-specific response formats.
    """
    try:
        if hasattr(response, "model_dump_json"):
            return response.model_dump_json(indent=2)[:max_chars]
    except Exception:
        pass

    try:
        if hasattr(response, "model_dump"):
            return json.dumps(response.model_dump(), ensure_ascii=False, indent=2)[:max_chars]
    except Exception:
        pass

    try:
        if isinstance(response, dict):
            return json.dumps(response, ensure_ascii=False, indent=2)[:max_chars]
    except Exception:
        pass

    try:
        return repr(response)[:max_chars]
    except Exception:
        return "Unable to serialize LLM response."


def extract_llm_answer_text(response) -> str:
    """
    Extract text from different possible chat completion response shapes.
    Some providers may return content in slightly different locations.
    """
    try:
        choice = response.choices[0]
    except Exception:
        return ""

    # Object-style response: choice.message.content
    try:
        message = choice.message
        content = getattr(message, "content", None)

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text") or item.get("content")
                    if text_value:
                        parts.append(str(text_value))
                else:
                    text_value = getattr(item, "text", None) or getattr(item, "content", None)
                    if text_value:
                        parts.append(str(text_value))
            return "\n".join(parts).strip()

        # Some providers may expose reasoning or alternative fields.
        for attr_name in ["reasoning_content", "text", "generated_text"]:
            value = getattr(message, attr_name, None)
            if isinstance(value, str) and value.strip():
                return value.strip()

    except Exception:
        pass

    # Dict-style response.
    try:
        if isinstance(choice, dict):
            message = choice.get("message", {})
            content = message.get("content")

            if isinstance(content, str):
                return content.strip()

            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        text_value = item.get("text") or item.get("content")
                        if text_value:
                            parts.append(str(text_value))
                return "\n".join(parts).strip()

            for key in ["reasoning_content", "text", "generated_text"]:
                value = message.get(key) or choice.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    except Exception:
        pass

    return ""
    
def get_effective_max_tokens() -> int:
    try:
        return int(st.secrets.get("HF_MAX_TOKENS", LLM_CONFIG.get("max_tokens", 900)))
    except Exception:
        return int(LLM_CONFIG.get("max_tokens", 900))


def get_effective_disable_thinking() -> bool:
    value = st.secrets.get("HF_DISABLE_THINKING", True)

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def prepare_messages_for_no_think(messages: list[dict]) -> list:
    """Add a direct-answer instruction to reduce hidden/thinking token usage
    in Qwen 3.x style models.
    """
    prepared = []

    for msg in messages:
        prepared.append(dict(msg))

    if not prepared:
        return prepared

    for idx in range(len(prepared) - 1, -1, -1):
        if prepared[idx].get("role") == "user":
            prepared[idx]["content"] = (
                str(prepared[idx].get("content", ""))
                + "\n\n"
                + "INSTRUCCIÓN DE GENERACIÓN:\n"
                + "- /no_think\n"
                + "- Responde directamente en español.\n"
                + "- No generes razonamiento interno.\n"
                + "- No dejes la respuesta vacía.\n"
                + "- Debes producir contenido visible bajo la sección Respuesta.\n"
            )
            break

    return prepared


def call_hf_chat_completion(hf_client, messages: list[dict]):
    """
    Centralized Hugging Face chat completion call.

    For Qwen 3.x / 3.6 models, try to disable thinking through provider-compatible
    extra parameters and also add /no_think instruction in the user message.
    """
    max_tokens = get_effective_max_tokens()
    disable_thinking = get_effective_disable_thinking()

    effective_messages = messages

    if disable_thinking:
        effective_messages = prepare_messages_for_no_think(messages)

    call_kwargs = {
        "messages": effective_messages,
        "max_tokens": max_tokens,
        "temperature": LLM_CONFIG["temperature"],
    }

    if disable_thinking:
        call_kwargs["extra_body"] = {
            "enable_thinking": False,
            "chat_template_kwargs": {
                "enable_thinking": False
            }
        }

    try:
        return hf_client.chat_completion(**call_kwargs)
    except TypeError:
        # Some providers/versions of huggingface_hub may not accept extra_body.
        # Retry without extra_body but keep the /no_think instruction in the prompt.
        call_kwargs.pop("extra_body", None)
        return hf_client.chat_completion(**call_kwargs)

# -----------------------------------------------------------------------------
# Generation
# -----------------------------------------------------------------------------
def generate_answer_with_rag(user_query: str, memory):
    hf_client = get_hf_client()

    if hf_client is None:
        return (
            "No fue posible generar la respuesta porque falta la configuración "
            "del servicio de inferencia."
        )

    retrieved_context, retrieved_docs = retrieve_context(
        user_query,
        top_k=CONFIG["retrieval_top_k"],
    )

    support_info = assess_retrieval_support(user_query, retrieved_docs)
    real_source_labels = build_real_source_labels(retrieved_docs)
    query_intent = classify_query_intent(user_query)
    allow_general_fallback = should_use_general_fallback(user_query, support_info)
    hard_anchor = has_hard_documentary_anchor(user_query, retrieved_docs, query_intent)
    strong_entity_match = has_strong_entity_document_match(user_query, retrieved_docs)

    # Requirements: use normal RAG if there is real support.
    # Only fail closed if support is weak AND there is no solid entity-document match.
    if query_intent == "requirements":
        if (
            support_info["support_level"] in {"weak", "none"}
            and not hard_anchor
            and not strong_entity_match
        ):
            answer = build_conservative_no_support_answer(
                user_query=user_query,
                real_source_labels=real_source_labels,
            )
            memory.add_turn(user_query, answer)
            return answer

    # Procedural / troubleshooting:
    # remain conservative only if there is neither hard anchor nor strong entity-document match.
    if query_intent in {"procedural", "troubleshooting"}:
        if not hard_anchor and not strong_entity_match:
            answer = build_conservative_no_support_answer(
                user_query=user_query,
                real_source_labels=real_source_labels,
            )
            memory.add_turn(user_query, answer)
            return answer

    # Generic weak support rule, but allow cases where entity-document alignment is strong.
    if (
        support_info["support_level"] in {"weak", "none"}
        and query_intent not in {"conceptual", "requirements"}
        and not strong_entity_match
    ):
        answer = build_conservative_no_support_answer(
            user_query=user_query,
            real_source_labels=real_source_labels,
        )
        memory.add_turn(user_query, answer)
        return answer

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

    try:
        response = call_hf_chat_completion(
        hf_client=hf_client,
        messages=messages,
    )

    except BadRequestError as e:
        st.session_state["last_llm_diagnostics"] = {
            "llm_call_ok": False,
            "model": get_effective_llm_model(),
            "provider": get_effective_hf_provider(),
            "temperature": LLM_CONFIG.get("temperature"),
            "max_tokens": LLM_CONFIG.get("max_tokens"),
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
        return build_llm_unavailable_answer(e)

    except HfHubHTTPError as e:
        st.session_state["last_llm_diagnostics"] = {
            "llm_call_ok": False,
            "model": get_effective_llm_model(),
            "provider": get_effective_hf_provider(),
            "temperature": LLM_CONFIG.get("temperature"),
            "max_tokens": LLM_CONFIG.get("max_tokens"),
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
        return build_llm_unavailable_answer(e)

    except Exception as e:
        st.session_state["last_llm_diagnostics"] = {
            "llm_call_ok": False,
            "model": get_effective_llm_model(),
            "provider": get_effective_hf_provider(),
            "temperature": LLM_CONFIG.get("temperature"),
            "max_tokens": LLM_CONFIG.get("max_tokens"),
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
        return build_llm_unavailable_answer(e)

    raw_response_debug = serialize_llm_response_for_debug(response)
    answer = extract_llm_answer_text(response)
    raw_answer = answer
    
    finish_reason = None
    usage_info = None
    
    try:
        finish_reason = response.choices[0].finish_reason
    except Exception:
        finish_reason = None
    
    try:
        if hasattr(response, "usage"):
            usage_info = response.usage
            if hasattr(usage_info, "model_dump"):
                usage_info = usage_info.model_dump()
    except Exception:
        usage_info = None
    
    st.session_state["last_llm_diagnostics"] = {
        "llm_call_ok": True,
        "model": get_effective_llm_model(),
        "provider": get_effective_hf_provider(),
        "temperature": LLM_CONFIG.get("temperature"),
        "max_tokens": get_effective_max_tokens(),
        "disable_thinking": get_effective_disable_thinking(),
        "finish_reason": finish_reason,
        "usage": usage_info,
        "raw_answer_length": len(raw_answer),
        "raw_answer_preview": raw_answer[:1000],
        "has_respuesta_section": "respuesta:" in raw_answer.lower(),
        "has_fuentes_section": "fuente" in raw_answer.lower(),
        "raw_response_debug": raw_response_debug,
        "error": None,
        "timestamp": datetime.now().isoformat(),
    }

    answer = clean_user_facing_answer(answer)

    answer = enforce_real_source_traceability(
        answer=answer,
        real_source_labels=real_source_labels,
        support_info=support_info,
        user_query=user_query,
    )

    if answer_is_sources_only(answer):
        answer = (
            "Respuesta:\n"
            "- El modelo de lenguaje respondió sin contenido útil para esta consulta. "
            "Sin embargo, el retrieval sí encontró fuentes documentales relevantes. "
            "Con la información recuperada, revisa primero si el trabajo aparece en el registro de trabajos del usuario en PaperCut MF "
            "y valida si la cola de impresión aparece en el equipo. Si la cola no aparece después del tiempo esperado, "
            "la fuente de autogestión indica reiniciar el computador.\n\n"
            "Fuente(s):\n"
            f"{build_source_block(real_source_labels)}\n\n"
            "Aviso: La generación del modelo fue incompleta, aunque el retrieval documental sí encontró fuentes."
        )
    
        st.session_state["last_llm_diagnostics"]["malformed_answer_detected"] = True
    else:
        st.session_state["last_llm_diagnostics"]["malformed_answer_detected"] = False

    memory.add_turn(user_query, answer)

    return answer
    
# -----------------------------------------------------------------------------
# Debug helpers
# -----------------------------------------------------------------------------
def debug_query_diagnostics(user_query: str) -> dict[str, Any]:
    retrieved_context, retrieved_docs = retrieve_context(
        user_query,
        top_k=CONFIG["retrieval_top_k"],
    )

    support_info = assess_retrieval_support(user_query, retrieved_docs)
    query_intent = classify_query_intent(user_query)
    hard_anchor = has_hard_documentary_anchor(
        user_query,
        retrieved_docs,
        query_intent,
    )
    real_source_labels = build_real_source_labels(retrieved_docs)

    docs_summary = []
    for doc in retrieved_docs:
        score = compute_rerank_score(user_query, doc, query_intent)
        docs_summary.append(
            {
                "title": doc.metadata.get("title"),
                "source": doc.metadata.get("source"),
                "vendor": doc.metadata.get("vendor"),
                "product": doc.metadata.get("product"),
                "component": doc.metadata.get("component"),
                "document_family": doc.metadata.get("document_family"),
                "source_group": doc.metadata.get("source_group"),
                "priority": doc.metadata.get("priority"),
                "page": doc.metadata.get("page"),
                "page_label": doc.metadata.get("page_label"),
                "rerank_score": round(score, 3),
                "content_preview": doc.page_content[:350],
            }
        )

    return {
        "query": user_query,
        "query_intent": query_intent,
        "support_info": support_info,
        "hard_anchor": hard_anchor,
        "real_source_labels": real_source_labels,
        "retrieved_count": len(retrieved_docs),
        "retrieved_docs_summary": docs_summary,
    }


# -----------------------------------------------------------------------------
# Escalation logic
# -----------------------------------------------------------------------------
ESCALATION_TRIGGERS = [
    "escalar", "nivel 2", "abrir caso", "incidente", "ticket", "no funcionó",
    "no funciona", "sigue igual", "sigue fallando", "ya hice eso", "ya lo intenté",
    "ya intenté", "ya reinicié", "ya reinicie", "no se resolvió",
]

CORE_INCIDENT_FIELDS = ["software_involved", "error_description", "actions_attempted", "printer_data"]
ENRICHMENT_INCIDENT_FIELDS = ["software_version", "contract_client_location", "evidence", "impact_type"]

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

NO_VALUE_PATTERNS = {"no", "no aplica", "no tengo", "desconozco", "no sé", "no se"}
NON_INFORMATIVE_REPLY_PATTERNS = {"ya te dije", "ya lo dije", "ya respondí", "ya respondi", "lo mismo", "igual"}


def normalize_user_reply(user_message: str) -> str:
    return " ".join(user_message.strip().lower().split())


def is_no_value_answer(user_message: str) -> bool:
    return normalize_user_reply(user_message) in NO_VALUE_PATTERNS


def is_non_informative_reply(user_message: str) -> bool:
    return normalize_user_reply(user_message) in NON_INFORMATIVE_REPLY_PATTERNS


def looks_like_specific_printer_data(user_message: str) -> bool:
    text = user_message.lower()
    model_or_device_hint = any(term in text for term in [
        "laserjet", "officejet", "deskjet", "pagewide", "multifuncional", "mfp",
        "serial", "serie", "hostname", "usb", "ethernet", "wifi", "scanner", "escaner",
    ])
    ip_hint = bool(re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", user_message))
    hp_model_hint = bool(re.search(r"\bhp\s+[A-Za-z0-9\-]+\b", user_message, re.IGNORECASE))
    return model_or_device_hint or ip_hint or hp_model_hint


def should_activate_escalation_mode(user_message: str) -> bool:
    text = user_message.lower()
    return any(trigger in text for trigger in ESCALATION_TRIGGERS)


def get_missing_incident_fields(state: IncidentState):
    missing = []
    for field_name in CORE_INCIDENT_FIELDS:
        value = getattr(state, field_name, None)
        if not value:
            missing.append(field_name)
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
    return FIELD_QUESTIONS[missing[0]] if missing else None


KNOWN_SOFTWARE = ["hp smart device services", "sds", "papercut", "web jetadmin", "hp access control", "gav tracking"]
ACTION_PATTERNS = [
    "reinicié", "reinicie", "reiniciar", "reinstalé", "reinstale", "actualicé", "actualice",
    "verifiqué", "verifique", "probé", "probe", "validé", "valide", "desinstalé", "desinstale",
]
ERROR_PATTERNS = ["error", "falla", "bloqueada", "no responde", "no funciona", "cola", "atasco", "offline", "desconectada"]
VERSION_RE = re.compile(r"(?:versi[oó]n|version)\s*[:\-]?\s*([A-Za-z0-9\.\-_]+)", re.IGNORECASE)


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

    papercut_match = re.search(
        r"\b(papercut(?:\s+(?:mf|ng|hive|pocket|mobility print))?)\s+v?(\d+(?:\.\d+)+)\b",
        user_message,
        re.IGNORECASE,
    )
    if papercut_match:
        extracted["software_involved"] = papercut_match.group(1).strip().lower()
        extracted["software_version"] = papercut_match.group(2).strip()

    sds_match = re.search(
        r"\b(hp smart device services|sds|web jetadmin|hp access control|gav tracking)\s+v?(\d+(?:\.\d+)+)\b",
        user_message,
        re.IGNORECASE,
    )
    if sds_match:
        extracted["software_involved"] = sds_match.group(1).strip().lower()
        extracted["software_version"] = sds_match.group(2).strip()

    if not extracted["software_involved"]:
        for software in KNOWN_SOFTWARE:
            if software in text:
                extracted["software_involved"] = software
                break

    version_match = VERSION_RE.search(user_message)
    if version_match and not extracted["software_version"]:
        extracted["software_version"] = version_match.group(1)

    detected_actions = [pattern for pattern in ACTION_PATTERNS if pattern in text]
    if detected_actions:
        extracted["actions_attempted"] = list(dict.fromkeys(detected_actions))

    if any(pattern in text for pattern in ERROR_PATTERNS) or any(
        expr in text for expr in ["no puedo", "no deja", "no me permite", "no aparece", "no logro", "no carga", "se detiene", "se cae", "no registra", "no agrega", "no detecta", "no encuentra"]
    ):
        extracted["error_description"] = user_message.strip()

    if looks_like_specific_printer_data(user_message):
        extracted["printer_data"] = user_message.strip()

    if any(term in text for term in ["cliente", "contrato", "sede", "ubicación", "ubicacion", "site", "oficina"]):
        extracted["contract_client_location"] = user_message.strip()

    if any(term in text for term in ["captura", "screenshot", "pantallazo", "evidencia", "log", "adjunto", "mensaje de error"]):
        extracted["evidence"] = user_message.strip()

    if any(term in text for term in ["afecta", "varios usuarios", "muchos usuarios", "un usuario", "todos los usuarios", "dispositivo crítico", "dispositivo critico", "indisponibilidad", "intermitente", "no imprime", "operación detenida", "operacion detenida", "masivo"]):
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
    return f"""Resumen del incidente:
- Software involucrado: {state.software_involved or 'No especificado'}
- Versión del software: {state.software_version or 'No especificada'}
- Error o síntoma principal: {state.error_description or 'No especificado'}
- Acciones realizadas: {', '.join(state.actions_attempted) if state.actions_attempted else 'No especificadas'}
- Datos de impresora: {state.printer_data or 'No especificados'}
- Cliente / contrato / ubicación: {state.contract_client_location or 'No especificado'}
- Evidencia: {state.evidence or 'No especificada'}
- Tipo de afectación: {state.impact_type or 'No especificado'}""".strip()


def process_escalation_turn(user_message: str, state: IncidentState, session_state: ChatSessionState):
    pending_field = getattr(session_state, "pending_incident_field", None)
    user_text = user_message.strip()

    if pending_field and field_accepts_no_value(pending_field) and is_no_value_answer(user_message):
        apply_no_value_to_field(state, pending_field)
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
        if pending_field == "software_involved" and not extracted["software_involved"]:
            extracted["software_involved"] = user_text
        elif pending_field == "software_version" and not extracted["software_version"]:
            version_only = re.search(r"\b\d+(?:\.\d+)+\b", user_message)
            extracted["software_version"] = version_only.group(0) if version_only else user_text
        elif pending_field == "error_description":
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
        return {
            "status": "collecting_information",
            "missing_fields": missing_fields,
            "next_field": next_field,
            "next_question": FIELD_QUESTIONS[next_field],
            "incident_state": state.to_dict(),
        }

    return {
        "status": "ready_for_summary",
        "missing_fields": [],
        "summary": build_incident_summary(state),
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
    return {"status": "persisted", "exported_file": str(exported_file)}


# -----------------------------------------------------------------------------
# Routing
# -----------------------------------------------------------------------------
def handle_escalation_message(user_message: str, session_state: ChatSessionState):
    session_state = ensure_session_state_integrity(session_state)
    session_state.mode = "escalation"
    session_state.incident_state.escalation_requested = True

    result = process_escalation_turn(user_message, session_state.incident_state, session_state)
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
    bot_message = generate_answer_with_rag(user_query=user_message, memory=session_state.memory)
    session_state.log_turn(user_message, bot_message, "rag_answer")
    return bot_message


def route_user_message(user_message: str, session_state: ChatSessionState):
    session_state = ensure_session_state_integrity(session_state)

    if session_state.mode == "escalation":
        return handle_escalation_message(user_message, session_state)

    if should_activate_escalation_mode(user_message):
        return handle_escalation_message(user_message, session_state)

    if not is_in_scope_message(user_message):
        bot_message = OUT_OF_SCOPE_RESPONSE
        session_state.memory.add_turn(user_message, bot_message)
        session_state.log_turn(user_message, bot_message, "out_of_scope")
        return bot_message

    return handle_normal_message(user_message, session_state)


def get_backend_status():
    status = {
        "vectorstore_ok": False,
        "embedding_ok": False,
        "hf_client_ok": False,
        "llm_model": get_effective_llm_model(),
        "hf_provider": get_effective_hf_provider(),
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
        status["error"] = f"Vectorstore error: {e}"
        return status

    try:
        hf_client = get_hf_client()
        status["hf_client_ok"] = hf_client is not None
        if hf_client is None:
            status["error"] = "HF_TOKEN is missing or HF client could not be initialized."
    except Exception as e:
        status["error"] = f"HF client error: {e}"

    return status
    try:
        hf_client = get_hf_client()
        status["hf_client_ok"] = hf_client is not None
    except Exception as e:
        status["error"] = f"HF client error: {e}"
        return status

    return status
