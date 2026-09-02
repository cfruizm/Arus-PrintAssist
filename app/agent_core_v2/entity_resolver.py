from __future__ import annotations
import importlib,re
from .models import EntityRef

class EntityResolver:
    """Uses the existing domain registry when available. No products are embedded here."""
    def __init__(self,registry_module="app.domain_registry"):
        self.registry_module=registry_module
        try:self.registry=importlib.import_module(registry_module)
        except Exception:self.registry=None
    def _from_detector(self,text):
        if not self.registry:return []
        for name in ("detect_entities_in_text","resolve_entities","detect_domain_entities"):
            fn=getattr(self.registry,name,None)
            if callable(fn):
                try:return fn(text) or []
                except Exception:continue
        return []
    def _indexes(self):
        if not self.registry:return []
        indexes=[]
        for kind,name in (("product","PRODUCT_ALIAS_INDEX"),("process","PROCESS_ALIAS_INDEX")):
            idx=getattr(self.registry,name,None)
            if isinstance(idx,dict):indexes.append((kind,idx))
        return indexes
    def resolve(self,text,proposal_entities=None):
        found=[]
        for raw in self._from_detector(text):
            if isinstance(raw,str):found.append(EntityRef("product",self._id(raw),raw,raw,.95,"registry_detector"))
            elif isinstance(raw,dict):
                name=str(raw.get("canonical_name") or raw.get("name") or raw.get("value") or "").strip()
                if name:found.append(EntityRef(str(raw.get("kind") or raw.get("type") or "product"),str(raw.get("canonical_id") or raw.get("id") or self._id(name)),name,str(raw.get("matched_text") or name),float(raw.get("confidence",.95)),"registry_detector"))
        lowered=str(text or "").casefold()
        for kind,index in self._indexes():
            for alias,target in index.items():
                if re.search(r"(?<!\w)"+re.escape(str(alias).casefold())+r"(?!\w)",lowered):
                    name=str(target.get("canonical_name") if isinstance(target,dict) else target); cid=str(target.get("canonical_id") if isinstance(target,dict) else self._id(name));found.append(EntityRef(kind,cid,name,str(alias),1.0,"registry_alias"))
        for raw in proposal_entities or []:
            if not isinstance(raw,dict):continue
            name=str(raw.get("canonical_name") or raw.get("name") or raw.get("value") or "").strip()
            if name:found.append(EntityRef(str(raw.get("kind") or raw.get("type") or "product"),str(raw.get("canonical_id") or raw.get("id") or self._id(name)),name,str(raw.get("matched_text") or name),float(raw.get("confidence",.7)),"interpreter"))
        result=[]
        for item in found:
            if not any(x.kind==item.kind and x.canonical_id==item.canonical_id for x in result):result.append(item)
        return result
    @staticmethod
    def _id(value):return re.sub(r"[^a-z0-9]+","_",str(value).casefold()).strip("_")
