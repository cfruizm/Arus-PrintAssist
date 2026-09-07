from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app.agent_core_v2.semantic_evidence_pipeline import SemanticEvidencePipeline
from app.agent_core_v2.models import ConversationState,EntityRef
from app.agent_core_v2.response import ResponseComposer
class EmptyJudge:
 def evaluate(self,*args):return {"ok":True,"assessments":[],"provider_result":{"ok":True}}
class Result:
 ok=True;text="";finish_reason="length";provider="test";model="test";usage={}
 def to_dict(self):return {"ok":self.ok,"text":self.text,"finish_reason":self.finish_reason}
class Gateway:
 def complete(self,*args):return Result()
def main():
 docs=[{"title":"Guide","url":"u","text":"relevant excerpt","metadata":{}}]
 pipe=SemanticEvidencePipeline(lambda q,n:docs,None,3,300);pipe.judge=EmptyJudge();state=ConversationState();decision=type("D",(),{"intent":"troubleshooting","entities":[]})()
 evidence=pipe.evaluate("technical request",decision,state,3)
 assert evidence["judge"]["complete"] is False and evidence["judge"]["assessed"]==0
 assert evidence["unassessed"][0]["semantic_assessment"]["applicability"]=="unassessed"
 assert not evidence["not_applicable"] and not evidence["citable"]
 state.active_topic.products=[EntityRef("product","p","Canonical Product")];state.technical_case.symptoms=["failure"];state.technical_case.affected_scope="multiple devices"
 answer=ResponseComposer(Gateway(),400).compose("request",decision,state,evidence)
 assert answer["fallback_reason"]=="response_truncated" and "multiple devices" in answer["text"]
 print("evidence and composition invariant tests passed")
if __name__=="__main__":main()
