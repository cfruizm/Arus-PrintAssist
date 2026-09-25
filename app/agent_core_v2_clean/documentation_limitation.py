from __future__ import annotations
from copy import deepcopy

def classify(retrieval, provider_result=None):
 r=retrieval or {};resolution=r.get("document_resolution") or {};verdict=r.get("evidence_verdict") or {};diagnostic=r.get("diagnostic_evidence") or r.get("evidence") or [];generation=r.get("generation_evidence") or []
 provider_result=provider_result or {}
 if provider_result and (not provider_result.get("ok",True) or str(provider_result.get("finish_reason") or "").casefold() in {"length","max_tokens"}):
  kind="provider_degraded"
 elif resolution.get("enabled") and resolution.get("status")=="not_found":kind="document_not_found"
 elif resolution.get("enabled") and resolution.get("status")=="ambiguous":kind="document_ambiguous"
 elif resolution.get("status")=="exact_match" and diagnostic and not verdict.get("accepted"):kind="document_found_operational_evidence_insufficient"
 elif diagnostic and not verdict.get("accepted"):kind="evidence_found_not_authorized"
 elif verdict.get("status")=="partial" or (generation and not verdict.get("accepted")):kind="evidence_partial"
 elif not diagnostic:kind="no_evidence_retrieved"
 else:kind="none"
 return {"schema_version":1,"kind":kind,"document_found":resolution.get("status")=="exact_match","document_title":((resolution.get("matches") or [{}])[0].get("title") if resolution.get("status")=="exact_match" else None),"diagnostic_evidence_count":len(diagnostic),"generation_evidence_count":len(generation),"verdict_status":verdict.get("status"),"verdict_reason":verdict.get("reason"),"provider_error":provider_result.get("error_code")}

def user_message(context):
 c=context or {};title=c.get("document_title") or "el documento solicitado";kind=c.get("kind")
 if kind=="document_not_found":return "No encontré el documento solicitado en el catálogo documental disponible."
 if kind=="document_ambiguous":return "Encontré más de un documento compatible con el identificador y no es seguro seleccionar uno automáticamente."
 if kind=="document_found_operational_evidence_insufficient":return f"Encontré {title}, pero los fragmentos disponibles no contienen el procedimiento solicitado con suficiente detalle para presentarlo como documentado."
 if kind=="evidence_found_not_authorized":return "Encontré fragmentos relacionados, pero no ofrecen soporte suficiente para presentar la respuesta solicitada como documentada."
 if kind=="evidence_partial":return "La documentación permite confirmar solo una parte de la respuesta; faltan pasos o validaciones para completarla."
 if kind=="provider_degraded":return "La evidencia estaba disponible, pero no fue posible generar la respuesta completa en este momento."
 if kind=="no_evidence_retrieved":return "No recuperé fragmentos documentales útiles para esta solicitud."
 return ""
