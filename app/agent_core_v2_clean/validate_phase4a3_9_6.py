from src.document_continuity import continuity_authority

def run():
 ctx={"source_identities":["doc://requirements"],"cited_evidence":[{"id":"R1","source":"doc://requirements"}]}
 u={"topic_relation":"same_topic","reference_relation":"current_subject"}
 b={"relation":"same_topic_refinement","previous_evidence_role":"primary"}
 c=continuity_authority(u,b,ctx)
 assert c["primary"] is True and c["preferred_sources"]==["doc://requirements"]
 assert c["answer_context"]["cited_evidence"][0]["id"]=="R1"
 new=continuity_authority({"topic_relation":"new_topic","reference_relation":"none"},{"relation":"new_topic","previous_evidence_role":"none"},ctx)
 assert new["primary"] is False and new["answer_context"]=={} and new["preferred_sources"]==[]
 import pathlib
 root=pathlib.Path(__file__).parent
 lab=(root/"lab_session.py").read_text()
 assert "preferred_sources=preferred_sources" in lab
 assert "document_continuity" in lab
 assert "cache_key = query.fingerprint" in lab
 assert "phase4a3_9_6_document_continuity_authority_recovery" in lab
 code=(root/"document_continuity.py").read_text().casefold()
 for forbidden in ("hp sds","vmware","hyper-v","firewall","papercut","da0390"):
  assert forbidden not in code
 print({"passed":8,"failed":0,"phase":"4A.3.9.6"})
if __name__=="__main__":run()
