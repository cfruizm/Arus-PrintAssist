from src.conversation_guardrails import rejected_association,reconcile_association,scope_gate

def run():
 base={'current_goal':'explicar proceso','goal_updates':{'subject':'Product Alpha'},'canonical_subject':'Product Alpha','subject_origin':'conversation_memory','topic_relation':'same_topic','user_act':'follow_up','domain_relevance':'in_scope','should_retrieve':True,'needs_clarification':False,'clarification_target':None}
 state={'active_topic':'explicar proceso','pending_goal':{'summary':'explicar proceso'}}
 u,e=reconcile_association('Eso no tiene nada que ver con Product Alpha',base,state)
 assert e['detected'] and not e['replacement_subject'] and u['canonical_subject'] is None and u['needs_clarification'] and not u['should_retrieve']
 assert u['clarification_target']=='producto, proceso o documento correcto'
 u2,e2=reconcile_association('No corresponde a Product Alpha, sino Product Beta',base,state)
 assert u2['canonical_subject']=='Product Beta' and u2['should_retrieve'] and not u2.get('needs_clarification',False)
 # Independent OOS remains blocked despite active printing context.
 oos=dict(base,domain_relevance='out_of_scope',user_act='new_request',topic_relation='new_topic',subject_origin='current_message',should_retrieve=True)
 g,trace=scope_gate('independent request',oos,state);assert trace['blocked'] and g['domain_relevance']=='out_of_scope' and not g['should_retrieve']
 # Only true referential follow-up may inherit scope.
 follow=dict(base,domain_relevance='out_of_scope',user_act='follow_up',topic_relation='same_topic',subject_origin='conversation_memory')
 g2,tr2=scope_gate('and that?',follow,state);assert not tr2['blocked'] and g2['domain_relevance']=='in_scope'
 # Uncertain independent request clarifies instead of answering.
 uncertain=dict(base,domain_relevance='uncertain',user_act='new_request',topic_relation='new_topic',subject_origin='current_message')
 g3,tr3=scope_gate('ambiguous independent request',uncertain,state);assert g3['needs_clarification'] and not g3['should_retrieve']
 # No campaign vocabulary in policy.
 policy=open(__file__.replace('validate_phase3d3.py','conversation_guardrails.py')).read()
 for forbidden in ('facturacion','template','HP SDS','PaperCut','DA0390'):assert forbidden.casefold() not in policy.casefold()
 print({'passed':6,'failed':0,'phase':'3D.3'})
if __name__=='__main__':run()
