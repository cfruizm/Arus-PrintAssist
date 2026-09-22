from __future__ import annotations
from copy import deepcopy
import re, unicodedata
_GENERIC={"como","para","una","uno","unos","unas","que","cual","cuales","existen","documentados","documentacion","informacion","usuario","proceso","procedimiento","metodo","metodos","detalle","detallar","realizar","realiza","describe","descripcion","paso","pasos","punto","puntos","final","finales","quiero","necesito","hacer","obtener","resumir","resume","the","how","for","documented","information","process","method","step","steps","point","points","summary"}
_SHORT={"pin","ews","usb","smb","wja","ipp","pcl","pdf","mf","dca","sds"}
_OPERATION={"asignar","consultar","actualizar","instalar","configurar","analizar","mostrar","generar","exportar","comparar","validar","validacion","validaciones","recuperar","descargar","importar","crear","visualizar","listar","resumir","distribuir","distribucion","procesar","ejecutar","escanear","requisito","requisitos","requirement","requirements","update","install","configure","assign","distribute","distribution"}
_CANON={"requirements":"requisito","requirement":"requisito","requisitos":"requisito","validaciones":"validacion","validation":"validacion","validations":"validacion","distribuir":"distribucion","distribution":"distribucion","actualizar":"actualizacion","update":"actualizacion","installation":"instalacion","install":"instalacion"}
def _norm(v):return unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold()
def _canon(t):
 t=_CANON.get(t,t)
 if len(t)>5 and t.endswith("es"):t=t[:-2]
 elif len(t)>4 and t.endswith("s"):t=t[:-1]
 return _CANON.get(t,t)
def _tokens(v):
 out=set()
 for token in re.findall(r"[a-z0-9]+",_norm(v)):
  if token in _GENERIC:continue
  if len(token)>=4 or token in _SHORT:out.add(_canon(token))
 return out
def _identity(i):return str(i.get("url") or i.get("source") or (i.get("metadata") or {}).get("canonical_url") or i.get("title") or "")
def _dedup(items):
 out=[];seen=set()
 for i in items:
  key=(_identity(i),str(i.get("page") or ""),_norm(i.get("text"))[:320])
  if key not in seen:seen.add(key);out.append(deepcopy(i))
 return out
def _request(message,u,r):
 if (u or {}).get("degraded"):return str(message or "")
 f=((r.get("query") or {}).get("fields") or {});rel=str(f.get("topic_relation") or (u or {}).get("topic_relation") or "")
 if rel=="new_topic":return " ".join((str(message or ""),str((u or {}).get("current_goal") or "")))
 g=(u or {}).get("goal_updates") or {}
 return " ".join(str(x or "") for x in (message,(u or {}).get("current_goal"),g.get("operation"),g.get("subject"),g.get("product"),f.get("contextual_operation")))
def _fit(item,wanted):
 title=_tokens(item.get("title"));content=title|_tokens(item.get("text"));covered=wanted&content;hits=wanted&title;sem=float((item.get("semantic_fit") or {}).get("score",0) or 0)
 return {"coverage":len(covered)/max(1,len(wanted)),"title_coverage":len(hits)/max(1,len(wanted)),"covered_count":len(covered),"title_hit_count":len(hits),"semantic_score":sem,"covered":sorted(covered),"title_hits":sorted(hits)}
def apply_unified_evidence_verdict(retrieval,message,understanding):
 out=deepcopy(retrieval or {});candidates=_dedup(out.get("diagnostic_evidence") or out.get("generation_evidence") or out.get("evidence") or []);wanted=_tokens(_request(message,understanding,out));scored=[]
 for item in candidates:
  fit=_fit(item,wanted);item["unified_evidence_fit"]={k:round(v,4) if isinstance(v,float) else v for k,v in fit.items()};scored.append((fit,item))
 scored.sort(key=lambda p:(p[0]["title_hit_count"],p[0]["covered_count"],p[0]["title_coverage"],p[0]["coverage"],p[0]["semantic_score"]),reverse=True)
 selected=[];accepted=False;status="insufficient";mode="internal_only";reason="no_operationally_aligned_evidence";best_fit,best=scored[0] if scored else ({},None)
 if best and wanted:
  available=_tokens(best.get("title"))|_tokens(best.get("text"));targets=wanted-_OPERATION;requested_short={x for x in wanted if x in _SHORT};short_ok=not requested_short or requested_short.issubset(available);target_ratio=len(targets&available)/max(1,len(targets)) if targets else 1.0;title_direct=best_fit["title_hit_count"]>=2;content_direct=best_fit["covered_count"]>=2 and best_fit["coverage"]>=.32;semantic_support=best_fit["semantic_score"]>=.10
  exact_document=title_direct and target_ratio>=.34 and short_ok
  relevant_answerable=short_ok and target_ratio>=.25 and (title_direct or (content_direct and semantic_support))
  if exact_document or relevant_answerable:
   accepted=True;identity=_identity(best);selected=[i for f,i in scored if _identity(i)==identity][:8];full=exact_document or best_fit["coverage"]>=.48 or len(selected)>=2;status="sufficient" if full else "partial_but_answerable";mode="documented" if full else "documented_partial";reason="direct_title_operation_match" if exact_document else "relevant_partial_documentation"
 for n,item in enumerate(selected,1):item["id"]=f"R{n}"
 verdict={"schema_version":4,"status":status,"mode":mode,"accepted":accepted,"reason":reason,"request_terms":sorted(wanted),"document_ids":list(dict.fromkeys(_identity(x) for x in selected)),"evidence_ids":[x["id"] for x in selected],"coverage":round(float(best_fit.get("coverage",0) if best else 0),4),"selected_evidence":deepcopy(selected),"rejected_count":max(0,len(candidates)-len(selected))}
 out["evidence_verdict"]=verdict;out["generation_evidence"]=deepcopy(selected);out["evidence"]=deepcopy(selected);sf=out.setdefault("semantic_fit",{});sf.update({"accepted_for_generation":accepted,"low_fit":not accepted,"generation_ids":verdict["evidence_ids"],"generation_count":len(selected),"selected_document":verdict["document_ids"][0] if verdict["document_ids"] else None,"decision_path":"unified_evidence_authority_v4","canonical_status":status});return out
