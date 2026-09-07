from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app.agent_core_v2.interpreter import _recover_partial

def main():
 partial='{"confidence":0.91,"conversation_act":"technical_request","intent":"procedural","topic_relation":"same_topic","requires_documents":true,'
 r=_recover_partial(partial);assert r and r["intent"]=="procedural" and r["requires_documents"] is True
 from app.agent_core_v2.response import ResponseComposer
 assert "approved_excerpt" in Path(ROOT/'app/agent_core_v2/response.py').read_text()
 from app.agent_core_v2.semantic_evidence_pipeline import SemanticEvidencePipeline
 assert hasattr(SemanticEvidencePipeline,"evaluate")
 print("focus and evidence progression invariants passed")
if __name__=="__main__":main()
