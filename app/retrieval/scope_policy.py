from __future__ import annotations

# Retrieval scope is architectural metadata, not question-specific logic.
SHARED_FAMILY_PRODUCTS = {
    "papercut_mf": {"family_ids": ["papercut_mf", "papercut_ng"], "vendor": "papercut"},
    "papercut_ng": {"family_ids": ["papercut_mf", "papercut_ng"], "vendor": "papercut"},
}

SPARSE_CONCEPTUAL_PRODUCTS = {
    "gav_tracking",
}

EDITORIAL_ROLE_TERMS = {
    "conceptual": {
        "positive_title": ("overview", "introduction", "about ", "what is", "product overview", "features", "architecture"),
        "negative_title": ("install", "instalacion", "instalación", "configur", "cuota", "quota", "registro", "conexion", "conexión", "troubleshoot", "error", "how to"),
    },
    "procedural": {
        "positive_title": ("install", "instalacion", "instalación", "configur", "setup", "adding", "agregar", "administrator guide", "training guide"),
        "negative_title": ("overview", "release history"),
    },
    "troubleshooting": {
        "positive_title": ("troubleshoot", "missing", "disappearing", "not being tracked", "stuck", "error", "issues", "problems"),
        "negative_title": ("features", "overview", "system requirements", "subscription", "installation"),
    },
    "requirements": {
        "positive_title": ("requirements", "requisitos", "compatibility", "compatibilidad"),
        "negative_title": ("troubleshoot", "installation guide"),
    },
    "warranty": {
        "positive_title": ("warranty", "garantia", "garantía"),
        "negative_title": ("installation", "overview"),
    },
}


def get_scope_policy(product_id: str | None, query_intent: str) -> dict:
    if product_id in SHARED_FAMILY_PRODUCTS:
        family=SHARED_FAMILY_PRODUCTS[product_id]
        return {"filter_policy":"shared_family","vendor":family["vendor"],"family_ids":family["family_ids"],"intent":query_intent}
    if product_id:
        return {"filter_policy":"exclusive_product","product_id":product_id,"intent":query_intent,"sparse_collection":product_id in SPARSE_CONCEPTUAL_PRODUCTS}
    return {"filter_policy":"unfiltered","intent":query_intent}


def classify_document_role(title: str, source_type: str, query_intent: str) -> tuple[str,float,list[str]]:
    text=f"{title} {source_type}".lower()
    rules=EDITORIAL_ROLE_TERMS.get(query_intent,{})
    positive=[term for term in rules.get("positive_title",()) if term in text]
    negative=[term for term in rules.get("negative_title",()) if term in text]
    if positive and not negative:return "intent_aligned",8.0,[f"title_positive:{term}" for term in positive]
    if negative and not positive:return "tangential",-10.0,[f"title_negative:{term}" for term in negative]
    if positive and negative:return "mixed",1.0,[f"title_positive:{term}" for term in positive]+[f"title_negative:{term}" for term in negative]
    return "neutral",0.0,[]
