from src.exact_document_retrieval import document_identifiers,exact_matches,query_variants,semantic_title
from src.unified_evidence_authority import apply_unified_evidence_verdict

def item(i,title,text,source,score=.3):
 return {'id':f'R{i}','title':title,'source':source,'url':source,'page':str(i),'text':text,'metadata':{'source_name':source.rsplit('/',1)[-1]},'semantic_fit':{'score':score}}
def verdict(items,message,subject,intent='procedural',exact=False):
 r={'query':{'fields':{'goal':message,'current_message':message,'details':{'subject':subject}}},'diagnostic_evidence':items,'generation_evidence':items,'semantic_fit':{'accepted_for_generation':True,'combined_quality':.7}}
 if exact:r['exact_document_match']={'matched':True,'identifiers':document_identifiers(subject)}
 return apply_unified_evidence_verdict(r,message,{'intent':intent,'canonical_subject':subject,'current_goal':message,'goal_updates':{'subject':subject}})['evidence_verdict']
def run():
 # Identifier and version are stripped generically to produce a semantic title query.
 subject='AB0390-6_V2 Analyze Operational Dashboard'
 assert semantic_title(subject)=='Analyze Operational Dashboard'
 variants=query_variants('I mean AB0390-6_V2 Analyze Operational Dashboard','',subject)
 assert 'Analyze Operational Dashboard' in variants and len(variants)==len({x.casefold() for x in variants})
 # Exact identity still prevents substitution by a similar code/title.
 ids=document_identifiers(subject)
 rows=[item(1,'AB0391-6 V2 Analyze Operational Dashboard','x','/d/AB0391.pdf'),item(2,'AB0390-6 V2 Analyze Operational Dashboard','x','/d/AB0390.pdf')]
 hits=exact_matches(rows,ids);assert len(hits)==1 and 'AB0390' in hits[0]['title']
 # Weak content-only procedural similarity is rejected.
 weak=[item(1,'Generic Administration Guide','install device locally point connection','/d/generic.pdf',.31),item(2,'Generic Administration Guide','create queue on remote host','/d/generic.pdf',.2)]
 v=verdict(weak,'How do I install a device point to point locally?','device point to point')
 assert not v['accepted'] and v['title_alignment_required'] and not v['procedural_content_support']
 # Strong title-aligned procedures remain accepted.
 good=[item(1,'Install device point to point','Steps to install device locally','/d/direct.pdf',.55),item(2,'Install device point to point','Create local port and select driver','/d/direct.pdf',.55)]
 assert verdict(good,'How do I install a device point to point locally?','device point to point')['accepted']
 # Exact corrected documents preserve authority even with OCR variance.
 exact=[item(1,'AB0400-6 V1 Install local driver','Create port','/d/AB0400.pdf',.2),item(2,'AB0400-6 V1 Install local driver','Select driver','/d/AB0400.pdf',.2)]
 assert verdict(exact,'Use AB0400-6 V1 for the procedure','AB0400-6 V1 Install local driver',exact=True)['accepted']
 # No benchmark/product vocabulary in production policy.
 policy=open(__file__.replace('validate_phase3c10.py','exact_document_retrieval.py')).read()+open(__file__.replace('validate_phase3c10.py','unified_evidence_authority.py')).read()
 for forbidden in ('DA0390','DA0421','PaperCut','Jetadmin','SIMP','punto a punto'):assert forbidden.casefold() not in policy.casefold()
 print({'passed':6,'failed':0,'phase':'3C.10'})
if __name__=='__main__':run()
