from src.exact_document_retrieval import document_identifiers,query_variants,exact_matches

def run():
 ids=document_identifiers('Quiero conocer AB0506-6_V1 procedimiento de credenciales')
 assert ids==['ab0506 6 v1']
 variants=query_variants('Quiero conocer AB0506-6_V1 procedimiento','', 'AB0506-6_V1 procedimiento')
 assert len(variants)>=4 and any(x=='ab05066v1' for x in variants)
 rows=[{'title':'AB0506-6 V1 Procedimiento de credenciales','source':'/docs/AB0506-6_V1.pdf','metadata':{}},{'title':'Otro manual','source':'/docs/other.pdf','metadata':{}}]
 assert len(exact_matches(rows,ids))==1
 assert not document_identifiers('cómo cambiar una credencial')
 policy=open(__file__.replace('validate_phase3c6.py','exact_document_retrieval.py')).read()
 for forbidden in ('IN0506','AUTOGESTION PIN','PaperCut','Web Print'):assert forbidden not in policy
 print({'passed':5,'failed':0,'phase':'3C.6'})
if __name__=='__main__':run()
