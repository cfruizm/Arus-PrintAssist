from types import SimpleNamespace
from .documented_router import maybe_generate_procedural
class Budget:
 def can_call(self,*a,**k): raise AssertionError("provider must not be called")
class Memory:
 def __init__(self): self.pending_goal=SimpleNamespace(status="active"); self.support_case=SimpleNamespace(attempts=[]); self.active_subject=None; self.subject_history=[]
 def to_dict(self): return {"pending_goal":{"status":self.pending_goal.status}}
def run():
 store={"memory":Memory(),"telemetry":{}}
 result={"understanding":{"domain_relevance":"out_of_scope","intent":"conceptual","topic_relation":"new_topic","user_act":"new_request"},"decision":{"action":"defer_to_retrieval"},"state_before":{},"functional_events":[]}
 out,trace=maybe_generate_procedural(result,"external question",None,Budget(),store)
 assert out["answer"]["mode"]=="scope_boundary"
 assert out["answer"]["knowledge_used"] is False
 assert out["retrieval"]["enabled"] is False
 assert out["internal_knowledge"]["enabled"] is False
 assert trace["reason"]=="out_of_scope_boundary"
 print({"passed":5,"failed":0,"phase":"3C.3"})
if __name__=="__main__": run()
