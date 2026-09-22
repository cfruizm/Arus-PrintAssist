import sys,types
m=types.ModuleType('app.agent_core_v2_clean.models');m.AgentResponse=object;sys.modules['app.agent_core_v2_clean.models']=m
from app.agent_core_v2_clean.evidence_sufficiency import assess_procedural_evidence,safe_partial_response

def ev(page,text):return {'page':str(page),'text':text}
def test_sufficient_multi_page_actionable_evidence():
 r={'ok':True,'evidence':[ev(1,'Abrir el archivo y validar la configuración. '*8),ev(2,'Copiar los datos, ejecutar el proceso y confirmar el resultado. '*8)],'procedural_expansion':{'ok':True,'same_document_only':True,'ordered':True}}
 a=assess_procedural_evidence(r);assert a.status=='sufficient' and a.generation_allowed
def test_partial_evidence_blocks_generation_but_is_candidate():
 r={'ok':True,'evidence':[ev(1,'Abrir el archivo y validar el resultado. '*5)],'procedural_expansion':{'ok':True,'same_document_only':True,'ordered':True}}
 a=assess_procedural_evidence(r);assert a.status=='partial' and not a.generation_allowed and a.internal_knowledge_candidate
def test_failed_or_mixed_evidence_is_insufficient():
 r={'ok':False,'evidence':[],'procedural_expansion':{'ok':False,'same_document_only':False,'ordered':False}}
 a=assess_procedural_evidence(r);assert a.status=='insufficient' and 'retrieval_or_expansion_failed' in a.reasons
def test_partial_response_does_not_invent_steps():
 a=assess_procedural_evidence({'ok':False,'evidence':[],'procedural_expansion':{}});text=safe_partial_response(a,{})
 assert 'No encontré evidencia documental suficiente' in text
def test_no_benchmark_or_product_terms():
 from pathlib import Path
 s=(Path('app/agent_core_v2_clean/evidence_sufficiency.py').read_text()+Path('app/agent_core_v2_clean/documented_router.py').read_text()).casefold()
 for x in ('web jetadmin','papercut','template_fac','pre-facturasimp','facturación'):assert x not in s
