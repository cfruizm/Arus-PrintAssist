from app.agent_core_v2_clean.evidence_authority import canonical_evidence_decision
from app.agent_core_v2_clean.scope_reconciler import reconcile_turn

def test_product_match_alone_is_not_sufficient():
 r={'generation_evidence':[{'id':'R1'}],'semantic_fit':{'alignment':{'product':1,'object':.1,'operation':0,'intent':.2,'coverage':1}}}
 assert canonical_evidence_decision(r,'procedural').status=='insufficient'
def test_operational_fit_can_be_sufficient():
 r={'generation_evidence':[{'id':'R1'},{'id':'R2'}],'semantic_fit':{'alignment':{'product':.8,'object':.8,'operation':.8,'intent':.8,'coverage':.8}}}
 assert canonical_evidence_decision(r,'procedural').accepted
def test_new_topic_is_never_downgraded():
 class U:user_act='request_elaboration';topic_relation='new_topic';domain_relevance='in_scope';needs_clarification=False;clarification_target=None;should_retrieve=True
 class M:active_topic='old';last_assistant_question='q'
 u,_=reconcile_turn(U(),M(),'new');assert u.topic_relation=='new_topic'
def test_orphan_elaboration_is_repaired():
 class U:user_act='request_elaboration';topic_relation='same_topic';domain_relevance='in_scope';needs_clarification=False;clarification_target=None;should_retrieve=True
 class M:active_topic=None;last_assistant_question=None
 u,c=reconcile_turn(U(),M(),'x');assert u.user_act=='new_request' and 'orphan_elaboration_to_new_request' in c
