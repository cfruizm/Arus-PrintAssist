import sys, types
app=types.ModuleType("app"); gateway=types.ModuleType("app.llm_gateway"); models=types.ModuleType("app.llm_gateway.models")
class LLMRequest:
    def __init__(self,*args,**kwargs): self.args=args; self.kwargs=kwargs
models.LLMRequest=LLMRequest
sys.modules.setdefault("app",app); sys.modules.setdefault("app.llm_gateway",gateway); sys.modules.setdefault("app.llm_gateway.models",models)
from src.models import ConversationMemory
from src.understanding import ConversationUnderstanding
from src.memory import apply_understanding

class Result:
    ok=True
    text='{"user_act": "attempt_result", "intent": "troubleshooting", "topic_relation": "same_topic", "domain_relevance": "in_scope", "current_goal": "Continue diagnosis", "goal_complete": false, "goal_updates": {}, "case_updates": [{"type": "attempted_action", "value": "inspect shared queue", "result": "failure continues", "outcome": "unchanged"}, {"type": "attempted_action", "value": "restart processing service", "result": "failure continues", "outcome": "unchanged"}], "needs_clarification": false, "clarification_target": null, "should_retrieve": true, "confidence": 1.0, "reasoning_summary": "two actions preserved", "canonical_subject": "Service", "subject_origin": "conversation_memory", "reference_relation": "current_subject", "requested_workflow": "none"}'
    provider='fixture';model='fixture';usage={'prompt_tokens':1,'completion_tokens':1,'total_tokens':2};finish_reason='stop';error_code=None
    def to_dict(self): return {'ok':True,'text':self.text,'provider':self.provider,'model':self.model,'usage':self.usage,'finish_reason':'stop','purpose':'agent_core_v2_clean_understanding'}
class Gateway:
    def complete(self,request): return Result()

def run():
    memory=ConversationMemory(); memory.active_topic='Active case'; memory.pending_goal.summary='Continue diagnosis'; memory.pending_goal.intent='troubleshooting'; memory.support_case.status='diagnosing'
    interpreter=ConversationUnderstanding(Gateway(),350)
    u=interpreter.interpret('compound technical update',memory)
    assert interpreter.contract_valid
    assert len(u.case_updates)==2
    apply_understanding(memory,u)
    assert len(memory.support_case.attempts)==2
    assert all(x['result']=='failure continues' and x['outcome']=='unchanged' for x in memory.support_case.attempts)
    actions={x['action'] for x in memory.support_case.attempts}
    assert actions=={'inspect shared queue','restart processing service'}
    import pathlib
    root=pathlib.Path(__file__).parent
    prompt=(root/'understanding.py').read_text().casefold()
    schema=(root/'contracts.py').read_text().casefold()
    assert 'preserve the full cardinality' in prompt
    assert 'never collapse several confirmed actions into only the last action' in prompt
    assert 'one attempted_action item per action' in schema
    for forbidden in ('papercut','find-me','print provider','cola del servidor','reinicié'):
        assert forbidden not in prompt and forbidden not in schema
    print({'passed':10,'failed':0,'phase':'4A.3.9.10.2'})
if __name__=='__main__': run()
