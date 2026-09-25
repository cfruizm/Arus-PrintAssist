from __future__ import annotations
import re,unicodedata
_CODE=re.compile(r"\b[A-Za-z]{2,}\d{3,}(?:[-_][A-Za-z0-9]+)*\b")
def norm(v):
 t=unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold();return " ".join(re.findall(r"[a-z0-9]+",t))
def document_identifiers(*values):
 out=[]
 for value in values:
  for m in _CODE.findall(str(value or "")):
   k=norm(m)
   if k and k not in out:out.append(k)
 return out
def query_variants(message,goal,subject):
 ids=document_identifiers(message,goal,subject);out=[];title=" ".join(str(subject or goal or message or "").split())
 for i in ids:
  for v in (i.replace(" ",""),"-".join(i.split()),"_".join(i.split()),i,title):
   if v and v.casefold() not in {x.casefold() for x in out}:out.append(v)
 return out[:8]
def exact_matches(items,ids):
 out=[]
 for x in items or []:
  m=x.get("metadata") or {};hay=norm(" ".join(str(v or "") for v in (x.get("title"),x.get("source"),x.get("url"),m.get("source_name"),m.get("title"))))
  if any(i in hay for i in ids):out.append(x)
 return out
