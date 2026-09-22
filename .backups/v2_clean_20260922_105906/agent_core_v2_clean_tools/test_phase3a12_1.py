import sys, types
sys.path.insert(0,'/mnt/data/build3121/patch/app')
from agent_core_v2_clean.entity_scope import normalize_scope
from agent_core_v2_clean.procedural_scope import constrain_generic_procedure
from agent_core_v2_clean.response_planner import build_response_plan
from agent_core_v2_clean.documented_fallback import build_documented_fallback

assert normalize_scope({'subject':'instalación de driver punto a punto'}).model is None
scope=normalize_scope({'device_model':'HP E52645','operating_system':'Windows 11 de 64 bits'})
assert (scope.manufacturer,scope.model,scope.operating_system,scope.architecture)==('HP','E52645','Windows 11','64 bits')

ev=[]
texts={2:'Identificar la dirección IP e ingresar a dispositivos e impresoras.',3:'Agregar una impresora local y seleccionar crear un puerto TCP/IP.',4:'Digitar la dirección IP y retirar la consulta automática del controlador.',5:'Seleccionamos Usar disco.',6:'Le damos la ruta donde quedó guardado el controlador. Seleccionamos el controlador y luego siguiente.',7:'Seleccionamos reemplazar el controlador actual. Ingresar el nombre y luego instalar.',8:'Colocamos No compartir esta impresora. Clic en Finalizar.'}
for i,(page,text) in enumerate(texts.items(),1):
 ev.append({'id':f'R{i}','title':'DA0400-6 V1 Instalar driver punto a punto','page':str(page),'source':'doc.pdf','url':'doc.pdf','text':text,'metadata':{'product':'sanitized_support_assets','vendor':'arus_internal','collection_name':'DA Arus','canonical_url':'doc.pdf'},'semantic_fit':{'score':0.63}})
r={'evidence':ev,'generation_evidence':ev,'semantic_fit':{'combined_quality':.70},'selection':{'quality':.70}}
u={'intent':'procedural','current_goal':'Explicar todos los pasos documentados para instalar un driver punto a punto','goal_updates':{'operation':'explicar','subject':'instalación de driver punto a punto'}}
r2=constrain_generic_procedure('Explícame todos los pasos documentados para instalar un driver punto a punto.',u,r)
assert r2['procedural_scope_guard']['restricted_to_example'] is False
assert r2['procedural_scope_guard']['direct_procedure_match_count'] == 7
plan=build_response_plan('Explícame todos los pasos documentados para instalar un driver punto a punto.',u,r2,{'status':'sufficient'})
assert plan.response_plan['mode']=='documented'
assert plan.request['missing_material_details']==[]
fb=build_documented_fallback({'generation_evidence':ev},reason='length')
assert fb and 'ruta donde quedó guardado' in fb['text']
assert 'páginas 2 a 8' in fb['text']
assert fb['degraded_reason']=='provider_output_truncated'
print('PASS scope-plan-fallback')
from agent_core_v2_clean.retrieval import ReadOnlyRetrieval, RetrievalQuery
mod=types.ModuleType('app.integration.document_expansion_adapter')
def same(q,source,k):
 return {'ok':True,'adapter':'fake.same_document','evidence':[{'title':'DA0400-6 V1 Instalar driver punto a punto','source':source,'url':source,'text':'Digitar la dirección IP y retirar la consulta automática del controlador.','metadata':{'page_label':'4','canonical_url':source}}]}
mod.retrieve_same_document=same
sys.modules['app.integration.document_expansion_adapter']=mod
built=RetrievalQuery('contexto',{'current_message':'¿Debo dejar activa la detección automática del controlador?','intent':'procedural'},'a')
current=RetrievalQuery('detección automática controlador',{'current_message':'¿Debo dejar activa la detección automática del controlador?','intent':'procedural'},'b')
def bad(q,k):return {'ok':True,'adapter':'global','evidence':[{'title':'HP Web Jetadmin','text':'Detección de dispositivos en red','metadata':{'page_label':'173'}}]}
out=ReadOnlyRetrieval(bad,10).search(built,current,['doc.pdf'])
assert out['selection']['chosen_mode']=='active_document'
assert out['selection']['active_document_reused'] is True
print('PASS active-document-continuity')
