from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import json
from app.agent_core_v2.interpreter import QwenInterpreter
from app.agent_core_v2.models import ConversationState
from app.llm_gateway.models import LLMResult
VALID=json.dumps({"conversation_act":"technical_request","intent":"troubleshooting","topic_relation":"new_topic","entities":[],"facts":[{"type":"symptom","value":"telemetria no reportada"},{"type":"affected_scope","value":"varios equipos"}],"requires_documents":True,"escalation_action":"none","confidence":0.94,"reasoning_summary":"failure and impact"})
class Gateway:
 def __init__(self,results):self.results=list(results);self.calls=[]
 def complete(self,request):self.calls.append(request);return self.results.pop(0)
def run():
 state=ConversationState()
 g=Gateway([LLMResult(False,error_code="invalid_request",model="qwen/qwen3.8-27b"),LLMResult(True,text=VALID,model="qwen/qwen3.8-27b")])
 i=QwenInterpreter(g,300);p=i.interpret("Falla tecnica con impacto en varios equipos",state)
 assert p.intent=="troubleshooting" and p.requested_action=="retrieve"
 assert len(g.calls)==2 and g.calls[0].response_schema and g.calls[1].response_schema is None
 assert i.last_trace["recovery_used"] and i.last_trace["parsed"]
 g2=Gateway([LLMResult(True,text=VALID,model="qwen/qwen3.8-27b")]);p2=QwenInterpreter(g2,300).interpret("Caso tecnico",state)
 assert p2.requested_action=="retrieve" and len(g2.calls)==1
 print("semantic resilience tests passed")
if __name__=="__main__":run()
