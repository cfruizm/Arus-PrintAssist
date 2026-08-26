from __future__ import annotations
import re,unicodedata
from urllib.parse import urldefrag
from app.domain_registry_v1 import PRODUCT_ENTITY_REGISTRY,PROCESS_ENTITY_REGISTRY
from app.retrieval.scope_policy import get_scope_policy
URL_RE=re.compile(r"https?://[^\s<>()]+",re.I)
def normalize(value):
    text=unicodedata.normalize("NFKD",str(value or "").lower());text="".join(c for c in text if not unicodedata.combining(c));return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9\s]"," ",text)).strip()
def contains(text,alias):
    alias=normalize(alias);return bool(alias and re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",text))
def detect(query,registry):
    text=normalize(query);found=[]
    for entity_id,item in registry.items():
        aliases=[item.get("canonical_name","")]+list(item.get("aliases") or [])
        if any(contains(text,a) for a in aliases):found.append({"entity_id":entity_id,"canonical_name":item.get("canonical_name",entity_id),"retrieval_hints":dict(item.get("retrieval_hints") or {})})
    return found
def extract_url(query):
    match=URL_RE.search(str(query or ""))
    if not match:return None
    clean,_=urldefrag(match.group(0).rstrip(".,;:!?)]}"));return clean.rstrip("/")
def build_plan(query,query_intent):
    products=detect(query,PRODUCT_ENTITY_REGISTRY);processes=detect(query,PROCESS_ENTITY_REGISTRY);product_id=products[0]["entity_id"] if products else None
    return {"mode":"original_query_with_scope_policy","semantic_query":query,"exact_url":extract_url(query),"products":products,"processes":processes,"scope_policy":get_scope_policy(product_id,query_intent)}
def build_filter(plan,counts):
    policy=plan["scope_policy"];products=plan["products"]
    if policy["filter_policy"]=="shared_family":
        vendor=policy.get("vendor");return {"vendor":vendor} if vendor and counts.get("vendor",{}).get(vendor,0)>=3 else None
    if policy["filter_policy"]=="exclusive_product" and products:
        hints=products[0].get("retrieval_hints") or {};clauses={}
        for field in ("product","vendor","component"):
            value=hints.get(field)
            if value and counts.get(field,{}).get(str(value).lower(),0)>=3:clauses[field]=value
        if len(clauses)==1:return clauses
        if clauses:return {"$and":[{k:v} for k,v in clauses.items()]}
    return None
