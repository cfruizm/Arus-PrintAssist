from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass,asdict
import re,unicodedata

_GENERIC={"como","para","una","uno","unos","unas","que","cual","cuales","existen","documentados","documentacion","informacion","impresion","impresora","usuario","proceso","procedimiento","metodo","metodos","detalle","realizar","actual","actualizar","explicar","analizar","saber","muestra","the","how","for","printer","printing","documented","information","process","method"}
_OPERATIONS={"asignar","consultar","actualizar","instalar","configurar","analizar","mostrar","generar","exportar","comparar","validar","recuperar","descargar","importar","crear","visualizar","listar","resumir"}
_SHORT={"pin","ews","usb","smb","wja","ipp","pcl","pdf"}

def _norm(v):return unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold()
def _tokens(v):
 out=[]
 for x in re.findall(r"[a-z0-9]+",_norm(v)):
  if x in _GENERIC:continue
  if len(x)>=4 or x in _SHORT:out.append(x)
 return set(out)
def _text(item):return " ".join((str(item.get("title") or ""),str(item.get("text") or "")))
def _identity(item):return str(item.get("url") or item.get("source") or (item.get("metadata") or {}).get("canonical_url") or item.get("title") or "")
def _dedup(items):
 out=[];seen=set()
 for item in items:
  key=(_identity(item),str(item.get("page") or ""),_norm(item.get("text") or "")[:300])
  if key in seen:continue
  seen.add(key);out.append(deepcopy(item))
 return out

def _request_text(message,understanding,retrieval):
 u=understanding or {};d=u.get("goal_updates") or {};f=((retrieval.get("query") or {}).get("fields") or {})
 return " ".join(str(x or "") for x in (message,u.get("current_goal"),d.get("operation"),d.get("subject"),d.get("product"),d.get("platform"),f.get("contextual_operation"),f.get("goal")))

def _score(item,wanted):
 title=_tokens(item.get("title"));body=_tokens(item.get("text"));available=title|body
 covered=wanted&available
 title_covered=wanted&title
 coverage=len(covered)/max(1,len(wanted));title_coverage=len(title_covered)/max(1,len(wanted))
 operations={x for x in wanted if x in _OPERATIONS};operation_match=1.0 if not operations else len(operations&available)/len(operations)
 semantic=float((item.get("semantic_fit") or {}).get("score",0) or 0)
 direct=bool(title_coverage>=0.5 or (coverage>=0.6 and operation_match>0) or (len(covered)>=2 and semantic>=0.25))
 return {"coverage":round(coverage,4),"title_coverage":round(title_coverage,4),"operation_match":round(operation_match,4),"semantic_score":semantic,"covered":sorted(covered),"direct":direct}

def apply_unified_evidence_verdict(retrieval,message,understanding):
 out=deepcopy(retrieval or {});candidates=_dedup(out.get("diagnostic_evidence") or out.get("generation_evidence") or out.get("evidence") or [])
 wanted=_tokens(_request_text(message,understanding,out));ranked=[]
 for item in candidates:
  fit=_score(item,wanted);item["unified_evidence_fit"]=fit;ranked.append((fit,item))
 ranked.sort(key=lambda x:(x[0]["direct"],x[0]["title_coverage"],x[0]["coverage"],x[0]["semantic_score"]),reverse=True)
 direct=[item for fit,item in ranked if fit["direct"]]
 if direct:
  doc=_identity(direct[0]);selected=[x for x in direct if _identity(x)==doc][:8]
  best=selected[0]["unified_evidence_fit"];status="sufficient" if best["coverage"]>=0.5 or best["title_coverage"]>=0.5 else "partial"
  mode="documented" if status=="sufficient" else "documented_partial";reason="direct_title_content_and_operation_match" if best["title_coverage"]>=0.5 else "direct_content_and_operation_match"
  accepted=True
 elif ranked and ranked[0][0]["coverage"]>=0.25 and ranked[0][0]["semantic_score"]>=0.25:
  non_operation={x for x in wanted if x not in _OPERATIONS}
  available=_tokens(_text(ranked[0][1]))
  if non_operation and not (non_operation & available):
   selected=[];status="insufficient";mode="internal_only";reason="operation_match_without_target_match";accepted=False
  else:
   selected=[ranked[0][1]];status="partial";mode="documented_partial";reason="related_but_incomplete_evidence";accepted=True
 else:
  selected=[];status="insufficient";mode="internal_only";reason="no_operationally_aligned_evidence";accepted=False
 for i,item in enumerate(selected,1):item["id"]=f"R{i}"
 verdict={"schema_version":1,"status":status,"mode":mode,"intent":str((understanding or {}).get("intent") or "unknown"),"request_terms":sorted(wanted),"document_ids":list(dict.fromkeys(_identity(x) for x in selected)),"evidence_ids":[x["id"] for x in selected],"coverage":max([x["unified_evidence_fit"]["coverage"] for x in selected] or [0.0]),"accepted":accepted,"reason":reason,"selected_evidence":deepcopy(selected),"rejected_count":max(0,len(candidates)-len(selected))}
 out["evidence_verdict"]=verdict;out["generation_evidence"]=deepcopy(selected);out["evidence"]=deepcopy(selected)
 sf=out.setdefault("semantic_fit",{});sf.update({"accepted_for_generation":accepted,"low_fit":not accepted,"generation_ids":verdict["evidence_ids"],"generation_count":len(selected),"selected_document":verdict["document_ids"][0] if verdict["document_ids"] else None,"decision_path":"unified_evidence_authority"})
 return out
