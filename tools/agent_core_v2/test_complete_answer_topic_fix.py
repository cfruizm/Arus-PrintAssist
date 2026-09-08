from app.agent_core_v2.response import ResponseComposer
from app.agent_core_v2.semantic_evidence_pipeline import SemanticEvidencePipeline
from app.agent_core_v2.decision import DecisionReconciler
def main():
 assert ResponseComposer(None).max_tokens>=620
 assert hasattr(SemanticEvidencePipeline,'_judge_all')
 assert DecisionReconciler is not None
 print('complete answer, hybrid knowledge and topic isolation modules import correctly')
if __name__=='__main__':main()
