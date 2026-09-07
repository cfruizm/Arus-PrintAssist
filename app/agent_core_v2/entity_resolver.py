from __future__ import annotations
import importlib,re
from .models import EntityRef
ALLOWED_KINDS={"product","component","process"}

def _norm(v):return re.sub(r"\s+"," ",str(v or "").casefold()).strip()
def _slug(v):return re.sub(r"[^a-z0-9]+","_",_norm(v)).strip("_")

class EntityResolver:
 def __init__(self,module="app.domain_registry"):
  try:self.registry=importlib.import_module(module)
  except Exception:self.registry=None

 def _registry_candidates(self,text):
  low=_norm(text);out=[]
  if not self.registry:return out
  for kind,index_name in (("product","PRODUCT_ALIAS_INDEX"),("component","COMPONENT_ALIAS_INDEX"),("process","PROCESS_ALIAS_INDEX")):
   index=getattr(self.registry,index_name,{})
   if not isinstance(index,dict):continue
   for alias,target in index.items():
    alias_text=_norm(alias)
    if alias_text and re.search(r"(?<!\w)"+re.escape(alias_text)+r"(?!\w)",low):
     if isinstance(target,dict):cid=str(target.get("canonical_id") or _slug(target.get("canonical_name") or alias));name=str(target.get("canonical_name") or alias)
     else:
      cid=str(target);name=str(alias)
      registries=("PRODUCT_ENTITY_REGISTRY","COMPONENT_ENTITY_REGISTRY","PROCESS_ENTITY_REGISTRY")
      for registry_name in registries:
       catalog=getattr(self.registry,registry_name,{})
       record=catalog.get(cid) if isinstance(catalog,dict) else None
       if isinstance(record,dict) and record.get("canonical_name"):
        name=str(record["canonical_name"]);break
     out.append((len(alias_text),EntityRef(kind,cid,name,str(alias),1.0,"registry")))
  return out

 def resolve(self,text,proposed=None):
  registry=self._registry_candidates(text);registry.sort(key=lambda x:x[0],reverse=True);selected=[]
  for length,item in registry:
   mention=_norm(item.matched_text)
   if any(item.kind==x.kind and mention and mention in _norm(x.matched_text) and len(mention)<len(_norm(x.matched_text)) for x in selected):continue
   if not any(x.kind==item.kind and x.canonical_id==item.canonical_id for x in selected):selected.append(item)
  # Model suggestions do not become canonical state unless resolved by a registry.
  return selected
