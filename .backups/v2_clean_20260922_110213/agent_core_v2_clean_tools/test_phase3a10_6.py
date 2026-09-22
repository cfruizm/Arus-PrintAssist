from app.agent_core_v2_clean.conceptual_route import prepare_conceptual_retrieval, conceptual_assessment

def ev(i,title,carried=False):
    return {'id':i,'title':title,'text':'','carried_from_previous_answer':carried}

def test_subject_shift_preserves_semantics_not_citations():
    r={'diagnostic_evidence':[ev('OLD','Universal driver',True),ev('X','Printer maintenance')], '_answer_context':{'goal':'previous concept','main_text_excerpt':'useful explanation','cited_ids':['OLD'],'cited_evidence':[{'id':'OLD'}],'source_titles':['Doc']}}
    out=prepare_conceptual_retrieval(r,{'relation':'same_topic','changed_dimensions':['subject']},{'goal_updates':{'subject':'page_description_language'}})
    c=out['_answer_context']
    assert c['main_text_excerpt']=='useful explanation'
    assert c['cited_ids']==[] and c['cited_evidence']==[] and c['citation_eligible'] is False
    assert out['conceptual_boundary']['conversation_context_preserved'] is True
    assert out['generation_evidence']==[]

def test_new_topic_removes_context_entirely():
    r={'diagnostic_evidence':[ev('A','Universal driver')], '_answer_context':{'goal':'old'}}
    out=prepare_conceptual_retrieval(r,{'relation':'new_topic','changed_dimensions':['subject']},{'goal_updates':{'subject':'print_driver'}})
    assert out['_answer_context']=={}

def test_direct_current_source_remains_eligible():
    r={'diagnostic_evidence':[ev('A','Universal driver installation'),ev('B','Printer maintenance')]}
    out=prepare_conceptual_retrieval(r,{'relation':'new_topic','changed_dimensions':['subject']},{'goal_updates':{'subject':'print_driver'}})
    assert [x['id'] for x in out['generation_evidence']]==['A']
    assert conceptual_assessment(out)['canonical_decision']['generation_mode']=='documented_plus_internal'

def test_no_direct_source_routes_internal_only():
    r={'diagnostic_evidence':[ev('A','Multifunction printer maintenance'),ev('B','Print queue installation')]}
    out=prepare_conceptual_retrieval(r,{'relation':'same_topic','changed_dimensions':['subject']},{'goal_updates':{'subject':'page_description_language'}})
    assert conceptual_assessment(out)['canonical_decision']['generation_mode']=='internal_only'
