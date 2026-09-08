from __future__ import annotations
import json
TECHNICAL={"conceptual","procedural","troubleshooting","requirements","architecture","warranty"}
SCHEMA={"type":"object","properties":{"intent":{"type":"string","enum":sorted(TECHNICAL|{"unknown"})},"conversation_act":{"type":"string"},"topic_relation":{"type":"string"},"requires_documents":{"type":"boolean"},"preserve_active_product":{"type":"boolean"},"confidence":{"type":"number"}},"required":["intent","conversation_act","topic_relation","requires_documents","preserve_active_product","confidence"]}

def suspicious(raw):
    intent=str(raw.get("intent") or "unknown"); act=str(raw.get("conversation_act") or "")
    summary=str(raw.get("reasoning_summary") or "").lower()
    return (act=="clarification" and intent in TECHNICAL and raw.get("requires_documents")) or (intent=="requirements" and any(x in summary for x in ("purpose","how to","procedural","definition")))

def reconcile(gateway,message,state,raw):
    if not suspicious(raw): return raw,{"used":False}
    from app.llm_gateway.models import LLMRequest
    payload={"message":message,"active_topic":state.active_topic.to_dict() if hasattr(state.active_topic,"to_dict") else {},"candidate":raw}
    prompt="Classify the current turn independently. conceptual=definition/purpose; procedural=how to do an action; requirements=prerequisites/compatibility/capacity; troubleshooting=failure/diagnosis. A clear technical request is not clarification. If the current request introduces a distinct subject not resolved by the active product, set preserve_active_product=false and independent_question. Return compact JSON only."
    res=gateway.complete(LLMRequest([{"role":"system","content":prompt},{"role":"user","content":json.dumps(payload,ensure_ascii=False,separators=(",",":"))}],"agent_core_v2_intent_reconcile",180,0.0,SCHEMA))
    if not res.ok:return raw,{"used":True,"ok":False}
    try:fixed=json.loads(str(res.text).strip())
    except Exception:return raw,{"used":True,"ok":False}
    return {**raw,**fixed},{"used":True,"ok":True,"intent_before":raw.get("intent"),"intent_after":fixed.get("intent"),"preserve_active_product":fixed.get("preserve_active_product")}
