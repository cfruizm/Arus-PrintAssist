import sys,types
from src.documentation_limitation import classify,user_message

def run():
 # Exact document exists, evidence exists, but authority rejects operation.
 r={'document_resolution':{'enabled':True,'status':'exact_match','matches':[{'title':'AB1000-2 Operational Guide'}]},'diagnostic_evidence':[{'id':'R1'}],'generation_evidence':[],'evidence_verdict':{'accepted':False,'status':'insufficient','reason':'no_operationally_aligned_evidence'}}
 c=classify(r);assert c['kind']=='document_found_operational_evidence_insufficient' and c['document_found']
 m=user_message(c);assert 'Encontré AB1000-2 Operational Guide' in m and 'no contienen el procedimiento' in m
 # Absent, ambiguous, partial, provider degraded are distinct.
 assert classify({'document_resolution':{'enabled':True,'status':'not_found'},'evidence_verdict':{}})['kind']=='document_not_found'
 assert classify({'document_resolution':{'enabled':True,'status':'ambiguous'},'evidence_verdict':{}})['kind']=='document_ambiguous'
 assert classify({'diagnostic_evidence':[{'id':'R1'}],'generation_evidence':[{'id':'R1'}],'evidence_verdict':{'accepted':False,'status':'partial'}})['kind'] in {'evidence_found_not_authorized','evidence_partial'}
 assert classify(r,{'ok':False,'error_code':'rate_limit'})['kind']=='provider_degraded'
 # Dynamic catalog resolution, no vector similarity for explicit IDs.
 class Col:
  def get(self,include=None):return {'metadatas':[{'title':'AB1000-2 V1 Operational Guide','source':'/kb/AB1000-2_V1.pdf','source_name':'AB1000-2_V1.pdf'}]}
 class VS:_collection=Col()
 app=types.ModuleType('app');backend=types.ModuleType('app.backend');backend.get_vectorstore=lambda:VS();app.backend=backend;sys.modules['app']=app;sys.modules['app.backend']=backend
 import src.document_resolver as dr;dr._CACHE.update({'at':0.0,'entries':[],'error':None});x=dr.resolve('Use AB1000-2_V1');assert x['status']=='exact_match' and x['catalog_size']==1
 # Production policy contains no campaign vocabulary.
 policy=open(__file__.replace('validate_phase3d2.py','documentation_limitation.py')).read()+open(__file__.replace('validate_phase3d2.py','document_resolver.py')).read()
 for forbidden in ('DA0390','DA0421','PaperCut','Jetadmin','SIMP'):assert forbidden.casefold() not in policy.casefold()
 print({'passed':7,'failed':0,'phase':'3D.2'})
if __name__=='__main__':run()
