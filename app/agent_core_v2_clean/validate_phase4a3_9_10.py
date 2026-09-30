import sys,types
app=types.ModuleType("app");gw=types.ModuleType("app.llm_gateway");models=types.ModuleType("app.llm_gateway.models")
class LLMRequest:
 def __init__(self,*a,**k):pass
models.LLMRequest=LLMRequest;sys.modules.setdefault("app",app);sys.modules.setdefault("app.llm_gateway",gw);sys.modules.setdefault("app.llm_gateway.models",models)
from src.documented_answer import _remove_contradicted_absence_claims
from src.semantic_fit import capture_answer_context

def ev(i,text,page="1"):return {"id":i,"title":"Guide","source":"doc://primary","page":page,"text":text,"metadata":{}}
def run():
 general="**Confirmed**\nGeneral hardware requirements are documented [R1].\n\n**Missing**\nThe documentation does not specify hardware requirements."
 repaired,changed,_=_remove_contradicted_absence_claims(general,"hardware requirements",{"canonical_subject":"Platform"},[ev("R1","General hardware requirements CPU memory storage.")])
 assert changed and "does not specify hardware requirements" not in repaired
 scoped="**Confirmed**\nGeneral hardware requirements are documented [R1].\n\n**Not specified**\nThe documentation does not specify additional environment-specific hardware requirements."
 repaired2,changed2,diag=_remove_contradicted_absence_claims(scoped,"hardware requirements",{"canonical_subject":"Platform"},[ev("R1","General hardware requirements CPU memory storage.")])
 assert not changed2 and "additional environment-specific" in repaired2 and diag["negative_claim_scope"]=="qualified"
 previous={"source_identities":["doc://primary"],"active_document_evidence_ledger":[ev("R1","Confirmed compatibility.","3")]}
 result={"answer":{"text":"Current network requirement [R2].","mode":"documented_answer","finish_reason":"stop"},"retrieval":{"evidence":[ev("R2","Current network requirement.","4")]},"understanding":{"current_goal":"Follow-up"},"document_continuity":{"primary":True}}
 ctx=capture_answer_context(result,previous)
 assert len(ctx["current_answer_cited_evidence"])==1 and len(ctx["active_document_evidence_ledger"])==2
 import pathlib
 root=pathlib.Path(__file__).parent;lab=(root/'lab_session.py').read_text();router=(root/'documented_router.py').read_text()
 assert 'accepted_documented_evidence_provider_failure_no_secondary_composer' in lab
 assert 'active_document_evidence_ledger' in router
 code=(root/'documented_answer.py').read_text().casefold()
 for forbidden in ('hp sds','vmware','hyper-v','papercut','da0390'):assert forbidden not in code
 print({'passed':10,'failed':0,'phase':'4A.3.9.10'})
if __name__=='__main__':run()
