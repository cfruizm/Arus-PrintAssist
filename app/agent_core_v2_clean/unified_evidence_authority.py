from __future__ import annotations
from copy import deepcopy
import re, unicodedata

_GENERIC={"como","para","una","uno","unos","unas","que","cual","cuales","existen","documentados","documentacion","informacion","impresion","impresora","usuario","proceso","procedimiento","metodo","metodos","detalle","detallar","realizar","actual","explicar","analizar","saber","muestra","necesito","quiero","the","how","for","printer","printing","documented","information","process","method"}
_SHORT={"pin","ews","usb","smb","wja","ipp","pcl","pdf","mf","dca","sds"}
_OPERATION={"asignar","consultar","actualizar","instalar","configurar","analizar","mostrar","generar","exportar","comparar","validar","recuperar","descargar","importar","crear","visualizar","listar","resumir"}

def _norm(value):return unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode().casefold()
def _tokens(value):
 out=set()
 for token in re.findall(r"[a-z0-9]+",_norm(value)):
  if token in _GENERIC:continue
  if len(token)>=4 or token in _SHORT:out.add(token)
 return out
def _identity(item):return str(item.get("url") or item.get("source") or (item.get("metadata") or {}).get("canonical_url") or item.get("title") or "")
def _item_text(item):return " ".join((str(item.get("title") or ""),str(item.get("text") or "")))
def _dedup(items):
 out=[];seen=set()
 for item in items:
  key=(_identity(item),str(item.get("page") or ""),_norm(item.get("text"))[:320])
  if key in seen:continue
  seen.add(key);out.append(deepcopy(item))
 return out
def _request_text(message,u,retrieval):
 u=u or {};d=u.get("goal_updates") or {};f=((retrieval.get("query") or {}).get("fields") or {})
 return " ".join(str(x or "") for x in (message,u.get("current_goal"),d.get("operation"),d.get("subject"),d.get("product"),f.get("contextual_operation"),f.get("goal")))
def _fit(item,wanted,distinctive):
 title=_tokens(item.get("title"));available=title|_tokens(item.get("text"));covered=wanted&available;title_hits=wanted&title;entity_hits=distinctive&title
 semantic=float((item.get("semantic_fit") or {}).get("score",0) or 0)
 carried=bool(item.get("carried_from_previous_answer"))
 return {"coverage":len(covered)/max(1,len(wanted)),"title_coverage":len(title_hits)/max(1,len(wanted)),"entity_hits":sorted(entity_hits),"entity_match":len(entity_hits),"semantic_score":semantic,"carried":carried,"covered":sorted(covered)}
def _distinctive_terms(candidates,wanted):
 counts={}
 for item in candidates:
  for token in (_tokens(item.get("title"))&wanted):counts[token]=counts.get(token,0)+1
 # Verbs cannot establish a product/entity identity by themselves.
 return {t for t,c in counts.items() if t not in _OPERATION and c < max(2,len(candidates))}
def apply_unified_evidence_verdict(retrieval,message,understanding):
 out=deepcopy(retrieval or {});candidates=_dedup(out.get("diagnostic_evidence") or out.get("generation_evidence") or out.get("evidence") or [])
 wanted=_tokens(_request_text(message,understanding,out));distinctive=_distinctive_terms(candidates,wanted);scored=[]
 for item in candidates:
  fit=_fit(item,wanted,distinctive);item["unified_evidence_fit"]={k:(round(v,4) if isinstance(v,float) else v) for k,v in fit.items()};scored.append((fit,item))
 # Explicit entity/title alignment outranks continuity bonuses from a previous answer.
 scored.sort(key=lambda pair:(pair[0]["entity_match"],pair[0]["title_coverage"],pair[0]["coverage"],pair[0]["semantic_score"],not pair[0]["carried"]),reverse=True)
 best_fit,best=(scored[0] if scored else ({},None));selected=[];accepted=False;status="insufficient";mode="internal_only";reason="no_operationally_aligned_evidence"
 if best:
  identity=_identity(best);entity_ok=best_fit["entity_match"]>0;coverage_ok=best_fit["coverage"]>=0.34;semantic_ok=best_fit["semantic_score"]>=0.25
  target_terms={x for x in wanted if x not in _OPERATION};available=_tokens(_item_text(best));target_ok=not target_terms or bool(target_terms&available)
  if entity_ok or (coverage_ok and semantic_ok and target_ok):
   selected=[item for fit,item in scored if _identity(item)==identity][:8];accepted=True
   full=best_fit["coverage"]>=0.5 or best_fit["title_coverage"]>=0.34 or best_fit["entity_match"]>=2
   status="sufficient" if full else "partial";mode="documented" if full else "documented_partial";reason="explicit_entity_title_match" if entity_ok else "direct_content_and_operation_match"
 for idx,item in enumerate(selected,1):item["id"]=f"R{idx}"
 verdict={"schema_version":2,"status":status,"mode":mode,"accepted":accepted,"reason":reason,"request_terms":sorted(wanted),"distinctive_title_terms":sorted(distinctive),"document_ids":list(dict.fromkeys(_identity(x) for x in selected)),"evidence_ids":[x["id"] for x in selected],"coverage":round(float(best_fit.get("coverage",0) if best else 0),4),"selected_evidence":deepcopy(selected),"rejected_count":max(0,len(candidates)-len(selected))}
 out["evidence_verdict"]=verdict;out["generation_evidence"]=deepcopy(selected);out["evidence"]=deepcopy(selected)
 sf=out.setdefault("semantic_fit",{});sf.update({"accepted_for_generation":accepted,"low_fit":not accepted,"generation_ids":verdict["evidence_ids"],"generation_count":len(selected),"selected_document":verdict["document_ids"][0] if verdict["document_ids"] else None,"decision_path":"unified_evidence_authority_v2"})
 return out
