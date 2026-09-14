from __future__ import annotations
from collections import OrderedDict
import re

def _clean(text):
 text=' '.join(str(text or '').split())
 text=re.sub(r'^DA\d[^•]*?(?=(?:OBJETIVO|ALCANCE|CONTENIDO|\d+\.|•))','',text,flags=re.I)
 return text.strip()

def _instruction(text):
 text=_clean(text)
 bullets=[x.strip(' .') for x in re.split(r'\s*•\s*',text) if x.strip()]
 useful=[]
 for x in bullets:
  if any(k in x.casefold() for k in ('aviso legal','informacion restringida','información restringida','objetivo','alcance','responsable','definiciones')):continue
  if len(x)>320:x=x[-320:]
  if x:useful.append(x)
 return useful[-1] if useful else text[-280:]

def build_documented_fallback(retrieval,reason='provider_degraded'):
 evidence=list((retrieval or {}).get('generation_evidence') or (retrieval or {}).get('evidence') or [])
 stages=[];sources=OrderedDict()
 for item in evidence:
  cid=str(item.get('id') or '');title=str(item.get('title') or 'Documento');page=str(item.get('page') or '')
  instruction=_instruction(item.get('text'))
  if not cid or not instruction:continue
  stages.append(f"{len(stages)+1}. {instruction} [{cid}]")
  sources[cid]=f"- [{cid}] {title}"+(f", página {page}" if page else '')
 if not stages:return None
 text=("**Procedimiento documentado**\n\n"+'\n'.join(stages)+"\n\n**Fuentes documentales**\n"+'\n'.join(sources.values()))
 return {'text':text,'mode':'procedural_documented_fallback','knowledge_used':True,'provider':None,'model':None,'usage':{},'finish_reason':'deterministic_fallback','documented_evidence_used':True,'internal_knowledge_used':False,'knowledge_mode':'documented_only','degraded':True,'degraded_reason':reason}
