from __future__ import annotations
import re, unicodedata
from urllib.parse import urldefrag
from app.domain_registry_v1 import PRODUCT_ENTITY_REGISTRY,PROCESS_ENTITY_REGISTRY
URL_RE=re.compile(r"https?://[^\s<>()]+",re.I)

def normalize(value):
    text=unicodedata.normalize("NFKD",str(value or "").lower()); text="".join(c for c in text if not unicodedata.combining(c)); return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9\s]"," ",text)).strip()
def contains(text,alias):
    alias=normalize(alias); return bool(alias and re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",text))
def detect(query,registry):
    text=normalize(query); found=[]
    for entity_id,item in registry.items():
        aliases=[item.get("canonical_name","")]+list(item.get("aliases") or [])
        if any(contains(text,a) for a in aliases): found.append({"entity_id":entity_id,"canonical_name":item.get("canonical_name",entity_id),"retrieval_hints":dict(item.get("retrieval_hints") or {})})
    return found
def exact_url(query):
    match=URL_RE.search(str(query or ""))
    if not match:return None
    clean,_=urldefrag(match.group(0).rstrip(".,;:!?)]}")); return clean.rstrip("/")
def build_plan(query):
    return {"mode":"exact_source" if exact_url(query) else "original_query_with_external_entity_policy","semantic_query":query,"exact_url":exact_url(query),"products":detect(query,PRODUCT_ENTITY_REGISTRY),"processes":detect(query,PROCESS_ENTITY_REGISTRY)}

def build_safe_filter(plan,metadata_counts):
    if not plan["products"]: return None
    hints=plan["products"][0].get("retrieval_hints") or {}; clauses={}
    for field in ("product","vendor","component"):
        value=hints.get(field)
        if value and (metadata_counts.get(field,{}) or {}).get(str(value).lower(),0)>=3: clauses[field]=value
    if not clauses:return None
    if len(clauses)==1:return clauses
    return {"$and":[{key:value} for key,value in clauses.items()]}
