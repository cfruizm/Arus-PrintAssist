from src.document_continuity import continuity_authority
from src.semantic_fit import apply_semantic_fit
from src.unified_evidence_authority import apply_unified_evidence_verdict

def run():
 ctx={"source_identities":["doc://authorized"],"cited_evidence":[{"id":"R1","source":"doc://authorized","text":"Prior evidence"}]}
 raw={"query":{"text":"current operation","fields":{"topic_relation":"same_topic_refinement","previous_evidence_role":"primary","user_act":"request_elaboration","current_message":"current operation","goal":"current operation"}},"evidence":[{"id":"R1","title":"Authorized guide","source":"doc://authorized","text":"Current operation network firewall port configuration requirements.","metadata":{}}],"_answer_context":ctx,"selection":{"quality":0.4}}
 fitted=apply_semantic_fit(raw,ctx)
 fitted["_answer_context"]=ctx
 out=apply_unified_evidence_verdict(fitted,"current operation network firewall",{"intent":"requirements","current_goal":"current operation","goal_updates":{}})
 assert out["_answer_context"]["source_identities"]==["doc://authorized"]
 assert out["evidence_verdict"]["accepted"] is True
 assert out["evidence_verdict"]["reason"]=="primary_document_current_turn_relevance"
 assert out["semantic_fit"]["previous_evidence_role"]=="primary"
 assert out["generation_evidence"]
 # New topic cannot inherit primary authority.
 raw2={"query":{"text":"different subject","fields":{"topic_relation":"new_topic","previous_evidence_role":"none","user_act":"new_request","current_message":"different subject","goal":"different subject"}},"evidence":raw["evidence"],"_answer_context":{},"selection":{"quality":0.4}}
 out2=apply_unified_evidence_verdict(apply_semantic_fit(raw2,{}),"different subject",{"intent":"requirements","current_goal":"different subject","goal_updates":{}})
 assert (out2.get("evidence_verdict") or {}).get("reason") != "primary_document_current_turn_relevance"
 import pathlib
 root=pathlib.Path(__file__).parent
 lab=(root/"lab_session.py").read_text()
 assert 'raw["_answer_context"] = deepcopy(answer_context)' in lab
 assert 'raw["query"]["fields"]["user_act"]' in lab
 code=(root/"unified_evidence_authority.py").read_text().casefold()
 for forbidden in ("hp sds","vmware","hyper-v","papercut","da0390"):
  assert forbidden not in code
 print({"passed":8,"failed":0,"phase":"4A.3.9.7"})
if __name__=="__main__":run()
