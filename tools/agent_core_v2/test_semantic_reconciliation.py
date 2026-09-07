from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.agent_core_v2.semantic_reconciler import contract_is_suspicious
from app.agent_core_v2.evidence_judge_policy import STRICT_EVIDENCE_POLICY

def main():
    assert contract_is_suspicious({"conversation_act":"clarification","intent":"procedural","requires_documents":True})
    assert contract_is_suspicious({"conversation_act":"technical_request","intent":"unknown","requires_documents":True})
    assert not contract_is_suspicious({"conversation_act":"technical_request","intent":"conceptual","requires_documents":True})
    assert "not merely its document title" in STRICT_EVIDENCE_POLICY
    source=(ROOT/'app/agent_core_v2/progressive_retrieval.py').read_text()
    assert "max_candidates" in source and "retrieval_retry" in source
    print("semantic reconciliation and progressive retrieval invariants passed")
if __name__=="__main__": main()
