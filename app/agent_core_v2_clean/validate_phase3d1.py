import sys,types
from src.document_resolver import identifiers,norm

def run():
 class Col:
  def get(self,include=None):
   return {'metadatas':[{'title':'AB1000-2 V1 Install local device','source':'/kb/AB1000-2_V1.pdf','source_name':'AB1000-2_V1.pdf'},{'title':'AB1001-2 V1 Install local device','source':'/kb/AB1001-2_V1.pdf','source_name':'AB1001-2_V1.pdf'}]}
 class VS:_collection=Col()
 app=types.ModuleType('app');backend=types.ModuleType('app.backend');backend.get_vectorstore=lambda:VS();app.backend=backend
 sys.modules['app']=app;sys.modules['app.backend']=backend
 import src.document_resolver as dr;dr._CACHE.update({'at':0.0,'entries':[],'error':None})
 a=dr.resolve('Use AB1000-2_V1');assert a['status']=='exact_match' and a['matches'][0]['source'].endswith('AB1000-2_V1.pdf')
 b=dr.resolve('Use AB1999-2');assert b['status']=='not_found'
 assert identifiers('AB1000-2_V1')==['ab1000 2 v1']
 assert norm('Á-B_1')=='a b 1'
 # Product/document independence in production resolver.
 policy=open(__file__.replace('validate_phase3d1.py','document_resolver.py')).read()
 for x in ('DA0390','DA0421','PaperCut','Jetadmin','SIMP'):assert x.casefold() not in policy.casefold()
 print({'passed':5,'failed':0,'phase':'3D.1'})
if __name__=='__main__':run()
