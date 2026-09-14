from app.agent_core_v2_clean.entity_scope import normalize_scope
from app.agent_core_v2_clean.procedural_recovery import compact_retrieval_for_retry

def test_combined_device_model_is_decomposed():
 s=normalize_scope({'device_model':'HP E52645','operating_system':'Windows 11 64 bits'})
 assert s.manufacturer=='HP';assert s.model=='E52645';assert s.operating_system=='Windows 11';assert s.architecture=='64 bits'
def test_explicit_manufacturer_wins():
 s=normalize_scope({'manufacturer':'Fabricante confirmado','device_model':'Alias E52645'})
 assert s.manufacturer=='Fabricante confirmado' and s.model=='E52645'
def test_recovery_retains_late_stages():
 evidence=[{'id':f'R{i}','page':str(i),'title':'Doc','text':('paso '+str(i)+' ')*100} for i in range(1,9)]
 out=compact_retrieval_for_retry({'generation_evidence':evidence})
 assert [x['id'] for x in out['generation_evidence']]==[f'R{i}' for i in range(1,9)]
 assert out['procedural_recovery_selection']['selected_count']==8
 assert all(len(x['text'])<=361 for x in out['generation_evidence'])
def test_recovery_does_not_mutate_original():
 evidence=[{'id':'R1','text':'x'*1000}];source={'generation_evidence':evidence};compact_retrieval_for_retry(source);assert len(source['generation_evidence'][0]['text'])==1000
