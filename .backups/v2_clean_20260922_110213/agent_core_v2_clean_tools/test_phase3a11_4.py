from app.agent_core_v2_clean.entity_scope import normalize_scope
from app.agent_core_v2_clean.documented_fallback import build_documented_fallback
from app.agent_core_v2_clean.citation_finalizer import enforce_answer_contract

def test_generic_subject_is_not_model():
 s=normalize_scope({'subject':'impresora'})
 assert s.model is None and s.manufacturer is None

def test_deterministic_fallback_uses_all_evidence():
 ev=[{'id':f'R{i}','title':'Manual','page':str(i),'text':f'• Ejecutar etapa {i}'} for i in range(1,9)]
 a=build_documented_fallback({'generation_evidence':ev},'rate_limited')
 assert a['mode']=='procedural_documented_fallback'
 assert all(f'[R{i}]' in a['text'] for i in range(1,9))
 assert a['documented_evidence_used'] and not a['internal_knowledge_used']

def test_fallback_survives_citation_contract():
 ev=[{'id':'R1','title':'Manual','page':'2','text':'• Finalizar instalación'}]
 a=build_documented_fallback({'generation_evidence':ev},'rate_limited')
 plan={'evidence_plan':{'documented_ids':['R1'],'citation_map':{},'citation_namespace':'canonical'},'response_plan':{'allow_documented_claims':True}}
 out,audit=enforce_answer_contract(a,plan)
 assert out['documented_evidence_used'] and audit['valid'] and audit['unknown_ids']==[]
