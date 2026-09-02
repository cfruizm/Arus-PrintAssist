import importlib,re
from .models import EntityRef
class EntityResolver:
 def __init__(self,module="app.domain_registry"):
  try:self.registry=importlib.import_module(module)
  except Exception:self.registry=None
 def resolve(self,text,proposed=None):
  out=[];low=str(text).casefold()
  if self.registry:
   for kind,name in (("product","PRODUCT_ALIAS_INDEX"),("process","PROCESS_ALIAS_INDEX")):
    idx=getattr(self.registry,name,{})
    if isinstance(idx,dict):
     for alias,target in idx.items():
      if re.search(r"(?<!\w)"+re.escape(str(alias).casefold())+r"(?!\w)",low):
       n=str(target.get("canonical_name") if isinstance(target,dict) else target);cid=str(target.get("canonical_id") if isinstance(target,dict) else re.sub(r"\W+","_",n.casefold()))
       out.append(EntityRef(kind,cid,n,str(alias),1.,"registry"))
  for x in proposed or []:
   if isinstance(x,dict):
    n=str(x.get("canonical_name") or x.get("name") or x.get("value") or "")
    if n:out.append(EntityRef(str(x.get("kind") or "product"),str(x.get("canonical_id") or re.sub(r"\W+","_",n.casefold())),n,str(x.get("matched_text") or n),float(x.get("confidence",.7)),"interpreter"))
  return list({(x.kind,x.canonical_id):x for x in out}.values())
