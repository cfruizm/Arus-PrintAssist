from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app.agent_core_v2.entity_resolver import EntityResolver
from app.agent_core_v2.semantic_evidence_pipeline import SemanticEvidencePipeline
from app.agent_core_v2.models import ConversationState
class Judge:
 def evaluate(self,*args):raise AssertionError("judge must not run without candidates")
def main():
 found=EntityResolver("app.domain_registry_v1").resolve("HP SDS afecta varios equipos",[{"kind":"component","name":"equipos","confidence":.99}])
 assert any(x.canonical_id=="hp_sds" for x in found)
 assert not any(x.canonical_id.startswith("provisional_") for x in found)
 pipe=SemanticEvidencePipeline(lambda q,n:[],None,3,300);pipe.judge=Judge()
 decision=type("D",(),{"intent":"troubleshooting","entities":[]})()
 result=pipe.evaluate("consulta",decision,ConversationState(),3)
 assert result["counts"]["retrieved"]==0 and result["judge"]["skipped"]
 print("streamlit lab boundary tests passed")
if __name__=="__main__":main()
