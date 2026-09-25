from src.topic_boundary import infer_topic_boundary
from src.unified_evidence_authority import apply_unified_evidence_verdict
from src.exact_document_retrieval import document_identifiers,exact_matches

def ev(i,title,text,page='1'):
 return {'id':f'R{i}','title':title,'source':'/docs/AB0506-6_V1.pdf','url':'/docs/AB0506-6_V1.pdf','page':page,'text':text,'metadata':{'source_name':'AB0506-6_V1.pdf'},'semantic_fit':{'score':.75}}
def run():
 # Explicit product switch must not inherit prior evidence as primary.
 prev={'pending_goal':{'summary':'assign credential in Platform A','known_details':{'subject':'Platform A'}},'active_subject':'Platform A','support_case':{'status':'idle'}}
 u={'current_goal':'assign credential in Platform B','intent':'procedural','user_act':'request_elaboration','topic_relation':'same_topic','canonical_subject':'Platform B','goal_updates':{'subject':'Platform B'}}
 b=infer_topic_boundary(prev,u)
 assert b.relation=='same_topic_changed_scope' and b.previous_evidence_role=='comparison_only'
 # Request-shell language must not become a missing operation.
 evidence=[ev(1,'AB0506-6 V1 Credential self-management','Step 1 open registration portal. Step 2 confirm corporate account.'),ev(2,'AB0506-6 V1 Credential self-management','Step 3 wait for invitation. Step 4 activate service.','2')]
 r={'query':{'fields':{'goal':'Obtain the documented procedure for credential self-management','current_message':'Give me the documented procedure','details':{'subject':'AB0506-6 V1 Credential self-management'}}},'diagnostic_evidence':evidence,'generation_evidence':evidence,'semantic_fit':{'accepted_for_generation':True,'combined_quality':.8},'exact_document_match':{'matched':True,'identifiers':['ab0506 6 v1'],'source':'/docs/AB0506-6_V1.pdf'}}
 out=apply_unified_evidence_verdict(r,'Give me the documented procedure',{'intent':'procedural','canonical_subject':'AB0506-6 V1 Credential self-management','current_goal':'Obtain documented procedure','goal_updates':{'subject':'AB0506-6 V1 Credential self-management'}})
 assert out['evidence_verdict']['accepted'] and out['evidence_verdict']['requested_operation_terms']==[]
 # Exact identity cannot match a neighboring document.
 ids=document_identifiers('AB0506-6_V1')
 assert exact_matches([{'title':'AB0296-6 V1 Other','source':'/docs/AB0296-6_V1.pdf','metadata':{}}],ids)==[]
 # Policies remain product and benchmark agnostic.
 policy=open(__file__.replace('validate_phase3c7.py','topic_boundary.py')).read()+open(__file__.replace('validate_phase3c7.py','unified_evidence_authority.py')).read()
 for forbidden in ('PaperCut','Print Evolve','IN0506','Web Print'):assert forbidden not in policy
 print({'passed':4,'failed':0,'phase':'3C.7'})
if __name__=='__main__':run()
