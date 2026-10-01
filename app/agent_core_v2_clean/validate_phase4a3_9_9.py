import sys,types,pathlib
app=types.ModuleType("app");gw=types.ModuleType("app.llm_gateway");models=types.ModuleType("app.llm_gateway.models")
class LLMRequest:
 def __init__(self,*a,**k):pass
models.LLMRequest=LLMRequest;sys.modules.setdefault("app",app);sys.modules.setdefault("app.llm_gateway",gw);sys.modules.setdefault("app.llm_gateway.models",models)
from src.semantic_fit import capture_answer_context
from src.documented_answer import _remove_contradicted_absence_claims

def ev(i,text,page="1"):return {"id":i,"title":"Authorized guide","source":"doc://primary","page":page,"text":text,"metadata":{}}
def run():
 previous={"source_identities":["doc://primary"],"cited_evidence":[ev("R1","Compatibility and minimum hardware requirements are confirmed.","3")]}
 result={"answer":{"text":"Current network requirements [R2].","mode":"documented_answer","finish_reason":"stop"},"retrieval":{"evidence":[ev("R2","Current network requirements.","4")]},"understanding":{"current_goal":"Current follow-up"},"document_continuity":{"primary":True}}
 ctx=capture_answer_context(result,previous)
 assert ctx["cumulative_evidence_count"]==2 and {x["page"] for x in ctx["cited_evidence"]}=={"3","4"}
 text="**Confirmed**\nCompatibility and minimum requirements are confirmed [R1].\n\n**Not specified**\nThe documentation does not specify minimum requirements.\n- CPU\n- Memory\n- Storage"
 repaired,changed,_=_remove_contradicted_absence_claims(text,"minimum requirements",{"canonical_subject":"Authorized subject"},[ev("R1","Minimum requirements CPU memory storage compatibility.")])
 assert changed and "does not specify" not in repaired and "- CPU" not in repaired
 assert "Compatibility and minimum requirements" in repaired and "Not specified" not in repaired
 root=pathlib.Path(__file__).parent
 lab=(root/"lab_session.py").read_text();ret=(root/"retrieval.py").read_text();doc=(root/"documented_answer.py").read_text().casefold()
 assert 'capture_answer_context(result, store.get("answer_context") or {})' in lab
 assert '"preferred_document_locked":True' in ret
 for forbidden in ("hp sds","vmware","hyper-v","papercut","da0390"):assert forbidden not in doc
 print({"passed":9,"failed":0,"phase":"4A.3.9.9"})
if __name__=="__main__":run()
