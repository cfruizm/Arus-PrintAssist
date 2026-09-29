from __future__ import annotations
import re,unicodedata,time
RX=re.compile(r'\b[A-Za-z]{2,}\d{3,}(?:[-_][A-Za-z0-9]+)*\b');CACHE={'at':0.0,'entries':[],'error':None}
def norm(v):return ' '.join(re.findall(r'[a-z0-9]+',unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().casefold()))
def identifiers(*values):
 out=[]
 for value in values:
  for x in RX.findall(str(value or '')):
   n=norm(x)
   if n and n not in out:out.append(n)
 return out
def catalog(force=False):
 now=time.time()
 if CACHE['entries'] and not force and now-CACHE['at']<900:return CACHE
 try:
  from app.backend import get_vectorstore
  vs=get_vectorstore();col=getattr(vs,'_collection',None) or getattr(vs,'collection',None);raw=col.get(include=['metadatas']);unique={}
  for m in raw.get('metadatas') or []:
   m=dict(m or {});src=str(m.get('canonical_url') or m.get('source') or m.get('source_name') or '')
   if not src:continue
   title=str(m.get('title') or m.get('source_name') or src.rsplit('/',1)[-1]);unique.setdefault(src,{'source':src,'title':title,'normalized':norm(' '.join((title,str(m.get('source_name') or ''),src))),'metadata':m})
  CACHE.update(at=now,entries=list(unique.values()),error=None)
 except Exception as e:CACHE.update(at=now,entries=[],error=f'{type(e).__name__}: {e}')
 return CACHE
def resolve(*values):
 ids=identifiers(*values);c=catalog();matches=[x for x in c['entries'] if ids and any(i in x['normalized'] for i in ids)];status='exact_match' if len(matches)==1 else 'ambiguous' if len(matches)>1 else 'not_found'
 return {'enabled':bool(ids),'identifiers':ids,'status':status,'matches':matches,'catalog_size':len(c['entries']),'error':c['error'],'strategy':'metadata_catalog_exact_identity_v1'}
def retrieve(resolution,query,k=24):
 if resolution.get('status')!='exact_match':return []
 try:
  from app.integration.document_expansion_adapter import retrieve_same_document
  return (retrieve_same_document(query,resolution['matches'][0]['source'],k) or {}).get('evidence') or []
 except Exception:return []
