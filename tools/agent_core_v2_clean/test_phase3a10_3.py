from app.agent_core_v2_clean.evidence_boundary import enforce_evidence_boundary,normalize_citation_groups,scoped_generation_instruction

def test_new_topic_removes_carried():
 r={'diagnostic_evidence':[{'id':'R1','carried_from_previous_answer':True},{'id':'R2'}],'semantic_fit':{}}
 assert [x['id'] for x in enforce_evidence_boundary(r,'new_topic')['generation_evidence']]==['R2']
def test_new_topic_without_current_blocks():
 r={'diagnostic_evidence':[{'id':'R1','carried_from_previous_answer':True}],'semantic_fit':{}}
 assert enforce_evidence_boundary(r,'new_topic')['semantic_fit']['accepted_for_generation'] is False
def test_scope_instruction(): assert 'No afirmes' in scoped_generation_instruction({'relation':'same_topic_changed_scope'})
def test_citations(): assert normalize_citation_groups('x [R4, R6]')=='x [R4][R6]'
