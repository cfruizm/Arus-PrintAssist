import json
from pathlib import Path
from .models import ConversationMemory
from .understanding import ConversationUnderstanding

class Result:
 def __init__(self,text):
  self.ok=True;self.text=text;self.error_code=None
 def to_dict(self):return {"ok":True,"text":self.text}
class Gateway:
 def __init__(self,text):self.text=text;self.calls=0
 def complete(self,request):self.calls+=1;return Result(self.text)

def run(path):
 data=json.loads(Path(path).read_text(encoding="utf-8"));turn=data["turns"][0]
 raw=turn["provider_trace"]["understanding"]["text"]
 gateway=Gateway(raw);engine=ConversationUnderstanding(gateway,220);memory=ConversationMemory()
 u=engine.interpret(turn["input"],memory)
 checks={
  "exact_runtime_contract_becomes_social":u.intent=="social" and u.user_act=="social",
  "recovery_precedes_conceptual_retrieval":u.should_retrieve is False,
  "operation_not_persisted":u.goal_updates=={},
  "single_understanding_call":gateway.calls==1,
  "runtime_contract_valid":engine.contract_valid is True,
  "structural_correction_recorded":"semantic_non_operational_opening_recovered_before_retrieval_policy" in engine.normalization.get("structural_corrections",[]),
 }
 failed=[k for k,v in checks.items() if not v]
 return {"phase":"4B.1.5","passed":len(checks)-len(failed),"failed":len(failed),"checks":checks,"normalized":u.to_dict()}
if __name__=="__main__":
 import sys
 result=run(sys.argv[1]);print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(1 if result["failed"] else 0)
