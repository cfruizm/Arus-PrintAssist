from src.request_reconciliation import reconcile,negative_constraints,filter_excluded
from src.topic_boundary import infer_topic_boundary
from src.exact_document_retrieval import document_identifiers,exact_matches,query_variants
from src.unified_evidence_authority import apply_unified_evidence_verdict

def item(i,title,text,source=None):
 source=source or '/docs/AB0401-6_V1.pdf'
 return {'id':f'R{i}','title':title,'source':source,'url':source,'page':str(i),'text':text,'metadata':{'source_name':source.rsplit('/',1)[-1]},'semantic_fit':{'score':.75}}
def run():
 # A source correction preserves the prior operation.
 before={'pending_goal':{'summary':'Explicar cómo instalar una impresora por servidor','known_details':{'subject':'impresora por servidor'}},'active_subject':'impresora por servidor'}
 u={'current_goal':'Usar AB0401-6 V1','canonical_subject':'AB0401-6 V1 Instalar impresora por servidor','goal_updates':{'subject':'AB0401-6 V1 Instalar impresora por servidor'},'topic_relation':'same_topic','intent':'procedural'}
 out,diag=reconcile('Me refiero a AB0401-6_V1 Instalar impresora por servidor',u,before)
 assert diag['preserved_previous_operation'] and 'Explicar cómo instalar' in out['current_goal'] and out['reference_relation']=='corrected_subject'
 # The corrected subject invalidates previous primary evidence.
 b=infer_topic_boundary(before,out);assert b.relation=='same_topic_changed_scope' and b.previous_evidence_role=='none'
 # Negative constraint extraction and evidence filtering.
 c=negative_constraints('pero no quiero usar Product Console');assert c==['Product Console']
 kept,rejected=filter_excluded([item(1,'Product Console Guide','x','/docs/product-console.pdf'),item(2,'Direct print server guide','x','/docs/direct.pdf')],c)
 assert len(kept)==1 and len(rejected)==1 and 'Direct' in kept[0]['title']
 u2=dict(u,negative_constraints=c,reference_relation='negative_constraint')
 b2=infer_topic_boundary(before,u2);assert b2.reason=='negative_constraint_invalidates_evidence' and b2.previous_evidence_role=='none'
 # Similar document names with distinct identifiers cannot substitute each other.
 ids=document_identifiers('AB0421-6_V1 Operation Tool')
 rows=[item(1,'AB0422-6 V1 Operation Tool Secure','x','/docs/AB0422-6.pdf'),item(2,'AB0421-6 V1 Operation Tool','x','/docs/AB0421-6.pdf')]
 hits=exact_matches(rows,ids);assert len(hits)==1 and 'AB0421' in hits[0]['title']
 # Exact source correction authorizes same-document procedural evidence.
 ev=[item(1,'AB0401-6 V1 Instalar impresora por servidor','Ejecutar e ingresar el servidor.'),item(2,'AB0401-6 V1 Instalar impresora por servidor','Seleccionar la impresora e instalar el controlador.')]
 ret={'query':{'fields':{'goal':out['current_goal'],'current_message':'Me refiero a AB0401-6_V1','details':{'subject':out['canonical_subject']}}},'diagnostic_evidence':ev,'generation_evidence':ev,'semantic_fit':{'accepted_for_generation':True,'combined_quality':.8},'exact_document_match':{'matched':True,'identifiers':['ab0401 6 v1']}}
 verdict=apply_unified_evidence_verdict(ret,'Me refiero a AB0401-6_V1',out)['evidence_verdict'];assert verdict['accepted']
 # Exact diagnostics retain variants and candidates.
 assert len(query_variants('Resumen AB0421-6_V1 Operation Tool','', 'AB0421-6_V1 Operation Tool'))>=3
 # Generic policy is benchmark-agnostic.
 policy=open(__file__.replace('validate_phase3c9.py','request_reconciliation.py')).read()+open(__file__.replace('validate_phase3c9.py','topic_boundary.py')).read()
 for forbidden in ('DA0401','DA0421','PaperCut','Web Jetadmin','SIMP'):assert forbidden not in policy
 print({'passed':7,'failed':0,'phase':'3C.9'})
if __name__=='__main__':run()
