from __future__ import annotations
import re,unicodedata
from collections import OrderedDict

def _norm(v):return unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold()
def _clean(text):return " ".join(str(text or "").replace("\n"," ").split())
def _method_label(text,page):
 raw=_clean(text)
 # Prefer an explicit short heading appearing before the first instruction.
 for part in re.split(r"[.:]",raw[:220]):
  part=part.strip(" -–—")
  words=part.split()
  if 1<=len(words)<=8 and any(x.isupper() and len(x)>=2 for x in words):return part
 return f"Alternativa documentada, página {page}" if page else "Alternativa documentada"
def _instruction(text):
 text=_clean(text)
 # Remove repeated document headers and preserve a bounded operational statement.
 chunks=re.split(r"(?<=[.!?])\s+",text)
 useful=[]
 for c in chunks:
  n=_norm(c)
  if any(x in n for x in ("aviso legal","informacion restringida","control de cambios","control de registros")):continue
  if len(c)>=22:useful.append(c)
  if len(useful)>=2:break
 return " ".join(useful)[:700]
def _pages(items):
 vals=[]
 for x in items:
  try:vals.append(int(str(x.get('page'))))
  except:pass
 vals=sorted(set(vals));return ", ".join(map(str,vals))
def build_documented_fallback(retrieval,reason="provider_degraded"):
 evidence=list((retrieval or {}).get("generation_evidence") or (retrieval or {}).get("evidence") or [])
 if not evidence:return None
 groups=OrderedDict()
 for item in evidence:
  label=_method_label(item.get("text"),item.get("page"));groups.setdefault(label,[]).append(item)
 lines=["**Respuesta documentada de respaldo**",""]
 # Never render evidence from different pages/methods as a single mandatory linear flow.
 for pos,(label,items) in enumerate(groups.items(),1):
  lines.append(f"**{pos}. {label}**")
  for item in items:
   text=_instruction(item.get("text"))
   if text:lines.append(f"- {text} [{item.get('id')}]")
  lines.append("")
 title=str(evidence[0].get("title") or evidence[0].get("source") or "Documento")
 lines.extend(["**Fuentes documentales**",f"- {title}, páginas {_pages(evidence)}" if _pages(evidence) else f"- {title}"])
 reason_map={"length":"provider_output_truncated","max_tokens":"provider_output_truncated","rate_limited":"rate_limited"}
 return {"text":"\n".join(lines).strip(),"mode":"procedural_documented_structured_fallback","knowledge_used":False,"finish_reason":"deterministic_structured_fallback","documented_evidence_used":True,"internal_knowledge_used":False,"knowledge_mode":"documented_only","degraded":True,"degraded_reason":reason_map.get(str(reason),str(reason or "provider_degraded"))}
