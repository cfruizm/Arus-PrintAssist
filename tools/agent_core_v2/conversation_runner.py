from __future__ import annotations
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.agent_core_v2.models import ConversationState
from app.agent_core_v2.turn_interpreter import ScriptedInterpreter
from app.agent_core_v2.turn_engine import TurnEngine

class BenchmarkResolver:
    def resolve(self,text,proposal_entities=None):
        from app.agent_core_v2.models import EntityRef
        return [EntityRef(str(x.get("kind","product")),str(x["canonical_id"]),str(x["canonical_name"]),str(x.get("matched_text","")),float(x.get("confidence",1.0)),"benchmark") for x in (proposal_entities or [])]

def run(path):
 data=json.loads(Path(path).read_text(encoding="utf-8"));results=[]
 for conv in data:
  state=ConversationState(conversation_id=conv["id"]);engine=TurnEngine(ScriptedInterpreter([x["proposal"] for x in conv["turns"]]),BenchmarkResolver());turns=[]
  for item in conv["turns"]:turns.append(engine.process_turn(item["message"],state).to_dict())
  results.append({"id":conv["id"],"turns":turns,"final_state":state.to_dict()})
 print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=="__main__":run(sys.argv[1])
