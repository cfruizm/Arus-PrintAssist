from app.agent_core_v2_clean.semantic_fit import apply_semantic_fit

def test_generation_evidence_isolated():
 r={'query':{'text':'secure access','fields':{'goal':'secure access'}},'selection':{'quality':0.5},'evidence':[{'id':'R1','title':'Access guide','source':'a','text':'secure authentication access'},{'id':'R2','title':'Billing guide','source':'b','text':'invoice totals'}]}
 out=apply_semantic_fit(r,{})
 assert out['generation_evidence']==out['evidence'] and len({x['source'] for x in out['evidence']})==1
 assert len(out['diagnostic_evidence'])==2

def test_followup_carries_previous_evidence():
 context={'source_identities':['a'],'cited_evidence':[{'id':'R1','title':'Access guide','source':'a','text':'verify card compatibility'}],'main_text_excerpt':'card based access'}
 r={'query':{'text':'what should I validate','fields':{'goal':'configure access','user_act':'follow_up'}},'selection':{'quality':0.1},'evidence':[{'id':'R2','title':'Other','source':'b','text':'unrelated'}]}
 out=apply_semantic_fit(r,context)
 assert out['semantic_fit']['carried_previous_evidence']==1
