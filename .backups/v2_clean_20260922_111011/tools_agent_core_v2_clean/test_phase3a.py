from pathlib import Path
import ast
from app.agent_core_v2_clean.models import ConversationMemory,TurnUnderstanding
from app.agent_core_v2_clean.memory import apply_understanding
from app.agent_core_v2_clean.policy import ConversationPolicy

def read(n):return Path('app/agent_core_v2_clean',n).read_text()
def u(**kw):
 base=dict(user_act='new_request',intent='conceptual',topic_relation='new_topic',domain_relevance='in_scope',current_goal='Explicar una solución',goal_complete=False,goal_updates={},case_updates=[],needs_clarification=False,clarification_target=None,should_retrieve=True,confidence=.9,reasoning_summary='ok',degraded=False);base.update(kw);return TurnUnderstanding(**base)
def test_syntax():
 for n in ('models.py','understanding.py','policy.py','memory.py','agent.py','response.py'):ast.parse(read(n))
def test_clear_request_does_not_ask():assert ConversationPolicy().decide(u(),ConversationMemory()).action=='defer_to_retrieval'
def test_material_missing_detail_asks_once():
 x=u(intent='procedural',needs_clarification=True,clarification_target='modalidad requerida');d=ConversationPolicy().decide(x,ConversationMemory());assert d.action=='ask_one_question' and d.question_target
def test_empty_target_never_asks():
 x=u(intent='procedural',needs_clarification=True,clarification_target=None);assert ConversationPolicy().decide(x,ConversationMemory()).action!='ask_one_question'
def test_waiting_user_state():
 m=ConversationMemory();apply_understanding(m,u(intent='procedural',needs_clarification=True,clarification_target='dato material'));assert m.pending_goal.status=='waiting_user' and m.pending_goal.missing_detail=='dato material'
def test_short_answer_preserves_goal():
 m=ConversationMemory(active_topic='Objetivo original');m.pending_goal.summary='Objetivo original';m.pending_goal.intent='procedural';m.pending_goal.status='waiting_user';m.last_assistant_question='Pregunta';apply_understanding(m,u(user_act='answer_to_question',intent='procedural',topic_relation='same_topic',current_goal='Objetivo original',goal_updates={'entorno':'nube'}));assert m.active_topic=='Objetivo original' and m.pending_goal.summary=='Objetivo original' and m.pending_goal.known_details['entorno']=='nube'
def test_prompt_explicitly_prevents_over_questioning():
 s=read('understanding.py')+read('response.py');assert 'merely personalize' in s and 'A clear self-contained conceptual request' in s
def test_no_product_specific_rules():
 s=''.join(read(n) for n in ('models.py','understanding.py','policy.py','memory.py','agent.py','response.py')).casefold()
 for x in ('papercut','epson','web jetadmin','tarjeta y pin','template_fac'):assert x not in s
