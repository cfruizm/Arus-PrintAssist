import sys,types
app=types.ModuleType("app");gateway=types.ModuleType("app.llm_gateway");models=types.ModuleType("app.llm_gateway.models")
class LLMRequest:
 def __init__(self,*args,**kwargs):self.args=args;self.kwargs=kwargs
models.LLMRequest=LLMRequest;sys.modules.setdefault("app",app);sys.modules.setdefault("app.llm_gateway",gateway);sys.modules.setdefault("app.llm_gateway.models",models)
from src.documented_answer import DocumentedAnswerComposer
from src.operational_coherence import normalize_generation_flags
class Result:
 ok=True;provider="fixture";model="fixture";usage={"prompt_tokens":10,"completion_tokens":25,"total_tokens":35};finish_reason="stop"
 text=("La fuente confirma compatibilidad general y requisitos mínimos [R1]. "
       "La documentación no especifica requisitos mínimos ni compatibilidad [R1].")
 def to_dict(self):return {"ok":True,"provider":self.provider,"model":self.model,"usage":self.usage,"finish_reason":self.finish_reason,"text":self.text,"purpose":"agent_core_v2_clean_documented_answer"}
class Gateway:
 def __init__(self):self.calls=0
 def complete(self,request):self.calls+=1;return Result()
def run():
 ev=[{"id":"R1","title":"Authorized guide","source":"doc://authorized","page":"3","text":"Compatibility and minimum requirements are confirmed for the supported environment.","metadata":{}}]
 r={"evidence_verdict":{"accepted":True,"selected_evidence":ev,"reason":"primary_document_current_turn_relevance"},"generation_evidence":ev,"evidence":ev,"_answer_context":{"source_identities":["doc://authorized"],"cited_evidence":ev},"_case_context":{"attempts":[]}}
 g=Gateway();c=DocumentedAnswerComposer(g,480);a=c.compose("What compatibility and minimum requirements are documented?",{"intent":"requirements","current_goal":"Review compatibility and requirements","canonical_subject":"Authorized subject","goal_updates":{},"user_act":"request_elaboration","topic_relation":"same_topic"},r)
 assert g.calls==1
 assert a.mode=="documented_answer_partial" and a.finish_reason=="negative_claim_repaired"
 assert "confirma compatibilidad" in a.text and "no especifica requisitos" not in a.text
 assert c.validation["contradicted_negative_claim_removed"] is True
 result={"retrieval":{"semantic_fit":{"accepted_for_generation":False,"low_fit":True},"evidence_verdict":{"accepted":True,"reason":"primary_document_current_turn_relevance"}},"evidence_decision":{},"evidence_sufficiency":{}}
 normalize_generation_flags(result);f=result["retrieval"]["semantic_fit"]
 assert f["accepted_for_generation"] is True and f["low_fit"] is False and f["previous_evidence_role"]=="primary"
 import pathlib
 root=pathlib.Path(__file__).parent;lab=(root/"lab_session.py").read_text();code=(root/"documented_answer.py").read_text().casefold()
 assert "accepted_evidence_completed_documented_attempt_is_terminal" in lab
 assert "authorized_documented_answer_is_terminal" in lab
 for forbidden in ("hp sds","vmware","hyper-v","papercut","da0390"):
  assert forbidden not in code
 print({"passed":8,"failed":0,"phase":"4A.3.9.8"})
if __name__=="__main__":run()
