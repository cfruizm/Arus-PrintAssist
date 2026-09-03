from __future__ import annotations
import importlib,re
from .models import EntityRef
ALLOWED_KINDS={"product","component","process"}
def _norm(v):return re.sub(r"\s+"," ",str(v or "").casefold()).strip()
def _id(v):return re.sub(r"[^a-z0-9]+","_",_norm(v)).strip("_")
class EntityResolver:
 def __init__(self,module="app.domain_registry"):
  try:self.registry=importlib.import_module(module)
  except Exception:self.registry=None
 def resolve(self,text,proposed=None):
  candidates=[];low=_norm(text)
  if self.registry:
   for kind,name in (("product","PRODUCT_ALIAS_INDEX"),("component","COMPONENT_ALIAS_INDEX"),("process","PROCESS_ALIAS_INDEX")):
    idx=getattr(self.registry,name,{})
    if not isinstance(idx,dict):continue
    for alias,target in idx.items():
     aliasn=_norm(alias)
     if aliasn and re.search(r"(?<!\w)"+re.escape(aliasn)+r"(?!\w)",low):
      cname=str(target.get("canonical_name") if isinstance(target,dict) and target.get("canonical_name") else target);cid=str(target.get("canonical_id") if isinstance(target,dict) and target.get("canonical_id") else _id(cname));candidates.append((len(aliasn),EntityRef(kind,cid,cname,str(alias),1.,"registry")))
  for x in proposed or []:
   if not isinstance(x,dict):continue
   kind=str(x.get("kind") or x.get("type") or "product");name=str(x.get("canonical_name") or x.get("name") or x.get("value") or "").strip()
   if kind in ALLOWED_KINDS and name:candidates.append((len(_norm(x.get("matched_text") or name)),EntityRef(kind,str(x.get("canonical_id") or _id(name)),name,str(x.get("matched_text") or name),float(x.get("confidence",.7)),"interpreter")))
  # Sort by explicit confidence, match length, then prefer interpreter exact entities.
  candidates.sort(key=lambda z:(z[1].confidence,z[0],z[1].source=="interpreter"),reverse=True);selected=[]
  for length,item in candidates:
   if any(x.kind==item.kind and x.canonical_id==item.canonical_id for x in selected):continue
   # Suppress a generic alias when its matched text is contained in a longer selected match.
   match=_norm(item.matched_text)
   if any(item.kind==x.kind and match and match in _norm(x.matched_text) and len(match)<len(_norm(x.matched_text)) for x in selected):continue
   selected.append(item)
  return selected
