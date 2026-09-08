from __future__ import annotations
import json
COVERAGE_SCHEMA={"type":"object","properties":{"complete":{"type":"boolean"},"covered_aspects":{"type":"array","items":{"type":"string"}},"missing_aspects":{"type":"array","items":{"type":"string"}},"broad_request":{"type":"boolean"},"same_document_followup":{"type":"boolean"}},"required":["complete","covered_aspects","missing_aspects","broad_request","same_document_followup"]}

def assess_coverage(gateway,query,intent,citable):
    from app.llm_gateway.models import LLMRequest
    passages=[{"title":x.get("title"),"source":x.get("url"),"text":str(x.get("text") or "")[:1200]} for x in citable]
    payload={"request":query,"intent":intent,"passages":passages}
    system="Determine answer completeness, independently from relevance. A directly relevant passage may still be partial. Broad requirement questions should normally cover all major categories explicitly available in the identified document, such as platform, runtime, network, accounts/services, firewall, operational conditions, and hardware when present. Do not require categories irrelevant to the request. Return JSON only."
    res=gateway.complete(LLMRequest([{"role":"system","content":system},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_coverage",180,0.0,COVERAGE_SCHEMA))
    if not res.ok:return {"complete":False,"covered_aspects":[],"missing_aspects":[],"broad_request":False,"same_document_followup":False,"error":"provider"}
    try:return json.loads(str(res.text).strip())
    except Exception:return {"complete":False,"covered_aspects":[],"missing_aspects":[],"broad_request":False,"same_document_followup":False,"error":"json"}

def same_document_query(original_query,coverage,documents):
    missing=", ".join(coverage.get("missing_aspects") or [])
    names=", ".join(dict.fromkeys(str(x.get("title") or "") for x in documents if x.get("title")))
    return f"Solicitud: {original_query}. Buscar en el mismo documento ({names}) información adicional para completar: {missing}."
