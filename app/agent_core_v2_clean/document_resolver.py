from __future__ import annotations
import re,unicodedata,time
_CODE=re.compile(r"\b[A-Za-z]{2,}\d{3,}(?:[-_][A-Za-z0-9]+)*\b")
_CACHE={"at":0.0,"entries":[],"error":None}
def norm(v):return " ".join(re.findall(r"[a-z0-9]+",unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold()))
def identifiers(*values):
 out=[]
 for value in values:
  for x in _CODE.findall(str(value or "")):
   n=norm(x)
   if n and n not in out:out.append(n)
 return out
def _identity(meta):return str(meta.get("canonical_url") or meta.get("source") or meta.get("source_name") or "")
def _catalog(force=False):
 now=time.time()
 if not force and _CACHE["entries"] and now-_CACHE["at"]<900:return _CACHE
 try:
  from app.backend import get_vectorstore
  vs=get_vectorstore();col=getattr(vs,"_collection",None) or getattr(vs,"collection",None)
  if col is None:raise RuntimeError("vectorstore_collection_unavailable")
  raw=col.get(include=["metadatas"]);unique={}
  for m in raw.get("metadatas") or []:
   m=dict(m or {});identity=_identity(m)
   if not identity:continue
   title=str(m.get("title") or m.get("source_name") or identity.rsplit("/",1)[-1]);hay=norm(" ".join((title,str(m.get("source_name") or ""),identity)))
   unique.setdefault(identity,{"source":identity,"title":title,"normalized":hay,"metadata":m})
  _CACHE.update({"at":now,"entries":list(unique.values()),"error":None})
 except Exception as exc:_CACHE.update({"at":now,"entries":[],"error":f"{type(exc).__name__}: {exc}"})
 return _CACHE
def resolve(*values):
 ids=identifiers(*values);cat=_catalog();matches=[e for e in cat["entries"] if ids and any(i in e["normalized"] for i in ids)]
 status="exact_match" if len(matches)==1 else "ambiguous" if len(matches)>1 else "not_found"
 return {"enabled":bool(ids),"identifiers":ids,"status":status,"matches":matches,"catalog_size":len(cat["entries"]),"error":cat["error"],"strategy":"metadata_catalog_exact_identity_v1"}
def retrieve(resolution,query,k=24):
 if resolution.get("status")!="exact_match":return []
 try:
  from app.integration.document_expansion_adapter import retrieve_same_document
  return (retrieve_same_document(query,resolution["matches"][0]["source"],k) or {}).get("evidence") or []
 except Exception:return []
