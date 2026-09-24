from src.unified_evidence_authority import apply_unified_evidence_verdict

def row(i,title,text,family='guide',product='sample_product'):
    return {'id':f'R{i}','title':title,'text':text,'source':title,'metadata':{'product':product,'document_family':family},'semantic_fit':{'score':0.2}}

def run():
    u={'intent':'conceptual','canonical_subject':'Sample Product','current_goal':'Explain Sample Product','goal_updates':{'subject':'Sample Product'}}
    retrieval={'diagnostic_evidence':[
        row(1,'Configure Advanced Feature in Sample Product',"Sample Product's Advanced Feature allows one narrow action."),
        row(2,'Sample Product Overview','Sample Product is a print monitoring platform that provides administration and reporting.','brochure'),
        row(3,'Sample Product Guide','It provides monitoring, device management and operational visibility.','guide'),
    ],'semantic_fit':{}}
    out=apply_unified_evidence_verdict(retrieval,'What is Sample Product?',u)
    assert out['evidence_verdict']['accepted']
    assert out['evidence_verdict']['reason']=='conceptual_subject_claim_coverage'
    assert any(x['title']=='Sample Product Overview' for x in out['evidence'])
    assert all(x['title']!='Configure Advanced Feature in Sample Product' for x in out['evidence'])
    print({'passed':4,'failed':0,'phase':'3C.2'})
if __name__=='__main__': run()
