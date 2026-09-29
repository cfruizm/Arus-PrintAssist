from src.models import ConversationMemory,TurnUnderstanding
from src.policy import ConversationPolicy
from src.understanding import ConversationUnderstanding
from src.documented_answer import DocumentedAnswerComposer
from src.cache_limits import enforce_cache_limits

class DummyGateway:pass

def run():
 m=ConversationMemory()
 u=TurnUnderstanding("new_request","conceptual","new_topic","in_scope","diagnose",False,{},[{"type":"symptom","value":"failure"}],False,None,True,1,"fixture")
 c=ConversationUnderstanding(DummyGateway(),220);u=c._normalize(u,m)
 assert u.intent=="troubleshooting" and "case_signal_promoted_operational_intent" in c.normalization["structural_corrections"]
 assert ConversationPolicy().decide(u,m).action=="diagnose_with_retrieval"
 store={name:{str(i):i for i in range(20)} for name in ("exact_turn_cache","retrieval_cache","documented_answer_cache","procedural_answer_cache","internal_knowledge_cache")};store["cache_metrics"]={}
 d=enforce_cache_limits(store);assert max(d["entries"].values())<=8 and d["evicted_this_pass"]
 import pathlib
 root=pathlib.Path(__file__).parent;doc=(root/"documented_answer.py").read_text();ret=(root/"retrieval.py").read_text();lab=(root/"lab_session.py").read_text()
 assert 'bool(cited) if not available_pages' in doc
 assert '{"procedural","requirements","troubleshooting"}' in ret
 assert 'AGENT_CORE_RETRIEVAL_CACHE_MAX_ENTRIES' in lab
 for forbidden in ("papercut","find-me","trabajos desaparecen","cola del servidor"):
  assert forbidden not in (root/"cache_limits.py").read_text().casefold()
 print({"passed":7,"failed":0,"phase":"4A.3.9.5"})
if __name__=="__main__":run()
