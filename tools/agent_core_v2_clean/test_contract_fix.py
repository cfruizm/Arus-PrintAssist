from types import SimpleNamespace
from app.agent_core_v2_clean.models import ConversationMemory
from app.agent_core_v2_clean.understanding import ConversationUnderstanding
from app.agent_core_v2_clean.telemetry import empty,add_result
class G:
 def __init__(self,text):self.text=text
 def complete(self,r):return SimpleNamespace(ok=True,text=self.text,error_code=None,to_dict=lambda:{'ok':True,'text':self.text,'purpose':'understanding','usage':{'prompt_tokens':10,'completion_tokens':3,'total_tokens':13},'latency_ms':1,'metadata':{}})
def test_empty_object_is_functional_failure_and_preserves_state():
 m=ConversationMemory(active_topic='existing');m.pending_goal.summary='existing';u=ConversationUnderstanding(G('{}'),300);x=u.interpret('new input',m)
 assert x.degraded and not u.contract_valid and m.active_topic=='existing'
 t=empty();add_result(t,u.last_provider_result,u.contract_valid);assert t['contract_failed_calls']==1 and t['functional_failed_calls']==1
def test_valid_compact_contract_parses():
 raw='{"user_act":"new_request","intent":"conceptual","topic_relation":"new_topic","domain_relevance":"in_scope","current_goal":"explain print tool","goal_complete":true,"goal_updates":{},"case_updates":[],"needs_clarification":false,"clarification_target":null,"should_retrieve":true,"confidence":0.9,"reasoning_summary":"clear request"}'
 u=ConversationUnderstanding(G(raw),300);x=u.interpret('x',ConversationMemory());assert u.contract_valid and x.intent=='conceptual'
