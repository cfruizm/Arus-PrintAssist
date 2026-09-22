from app.agent_core_v2_clean.conceptual_route import prepare_conceptual_retrieval,conceptual_assessment,must_preempt_documented_answer

def test_new_concept_clears_previous_context():
 r={'diagnostic_evidence':[{'id':'R0','carried_from_previous_answer':True},{'id':'R1'}],'_answer_context':{'goal':'old'}}
 out=prepare_conceptual_retrieval(r,'new_topic')
 assert out['_answer_context']=={} and [x['id'] for x in out['generation_evidence']]==['R1']
def test_conceptual_always_uses_controlled_synthesis():
 assert must_preempt_documented_answer({'intent':'conceptual'})
 a=conceptual_assessment({'generation_evidence':[{'id':'R1'}]})
 assert a['internal_knowledge_candidate'] is True
 assert a['canonical_decision']['generation_mode']=='documented_plus_internal'
def test_no_evidence_uses_internal_only():
 a=conceptual_assessment({'generation_evidence':[]})
 assert a['canonical_decision']['generation_mode']=='internal_only'
