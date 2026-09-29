import sys,types
app=types.ModuleType("app");gateway=types.ModuleType("app.llm_gateway");models=types.ModuleType("app.llm_gateway.models")
class LLMRequest:
 def __init__(self,*args,**kwargs):self.args=args;self.kwargs=kwargs
models.LLMRequest=LLMRequest;sys.modules.setdefault("app",app);sys.modules.setdefault("app.llm_gateway",gateway);sys.modules.setdefault("app.llm_gateway.models",models)
from src.documented_answer import DocumentedAnswerComposer,safe_cited_partial
class Result:
 ok=True;provider="fixture";model="fixture";usage={"prompt_tokens":10,"completion_tokens":20,"total_tokens":30};finish_reason="length"
 def __init__(self,text):self.text=text
 def to_dict(self):return {"ok":self.ok,"text":self.text,"provider":self.provider,"model":self.model,"usage":self.usage,"finish_reason":self.finish_reason,"purpose":"agent_core_v2_clean_documented_answer"}
class Gateway:
 def __init__(self,text):self.text=text;self.calls=0
 def complete(self,request):self.calls+=1;return Result(self.text)
def evidence():
 return [{"id":"R1","title":"Web KB","url":"https://example.com/kb","source":"https://example.com/kb","page":"","text":"Validate verify configure confirm requirement compatible install update save open. "*5,"metadata":{"canonical_url":"https://example.com/kb"}}]
def retrieval():return {"generation_evidence":evidence(),"evidence":evidence(),"evidence_verdict":{"selected_evidence":evidence()},"_answer_context":{},"_case_context":{"attempts":[]}}
def understanding():return {"intent":"troubleshooting","current_goal":"Diagnose","user_act":"new_request","topic_relation":"new_topic"}
def run():
 partial,cited=safe_cited_partial("Complete claim [R1]. Incomplete",["R1"],"length");assert partial.endswith("[R1]") and cited==["R1"]
 g1=Gateway("Complete documented claim [R1]. Incomplete ending");a1=DocumentedAnswerComposer(g1,480).compose("diagnose",understanding(),retrieval());assert a1.mode=="documented_answer_partial" and a1.finish_reason=="safe_partial" and g1.calls==1
 g2=Gateway("Truncated output without a complete citation");a2=DocumentedAnswerComposer(g2,480).compose("diagnose",understanding(),retrieval());assert a2.mode=="documented_truncation_safe_defer" and a2.finish_reason=="safe_defer" and g2.calls==1
 assert a2.text.strip() and "https://example.com/kb" in a2.text
 import pathlib
 root=pathlib.Path(__file__).parent;lab=(root/"lab_session.py").read_text();code=(root/"documented_answer.py").read_text().casefold()
 assert "documented_truncation_safe_defer" in lab and "authorized_documented_answer_is_terminal" in lab
 for phrase in ("papercut","find-me","cola del servidor","trabajos desaparecen"):assert phrase not in code
 print({"passed":9,"failed":0,"phase":"4A.3.9.4"})
if __name__=="__main__":run()
