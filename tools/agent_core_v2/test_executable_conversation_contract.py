from types import SimpleNamespace
from app.agent_core_v2.models import ConversationState,CanonicalDecision
from app.agent_core_v2.response import ResponseComposer
from app.agent_core_v2.conversation_planner import ConversationPlanner
from app.agent_core_v2.adaptive_controller import AdaptiveCostRouteController
class G:
 def __init__(self,answers):self.answers=list(answers)
 def complete(self,request):return SimpleNamespace(ok=True,text=self.answers.pop(0),provider='test',model='test',usage={},finish_reason='stop')
def d(action='retrieve',intent='procedural'):return CanonicalDecision(action,intent,'technical_request','same_topic',[],[],None,.9,[],False,action=='retrieve')
def test_out_of_scope_always_has_visible_route():
 x=d('decline_out_of_scope','out_of_scope');p=AdaptiveCostRouteController().plan_before_retrieval(x,ConversationState())
 assert p.route=='compose_out_of_scope'
 assert ResponseComposer(None).compose_conversation('x',x,ConversationState())['text']
def test_unsupported_ui_route_is_regenerated_without_exact_path():
 c=ResponseComposer(G(['Ve a Administración > Usuarios > Editar y activa el campo PIN.','Necesito precisar qué tipo de acceso quieres configurar: ¿autenticación de usuario, imputación de costos o administración?']))
 plan=ConversationPlanner().build(d(),ConversationState(),{})
 a=c.compose('configurar acceso',d(),ConversationState(),{},plan)
 assert a['unsupported_precision_regenerated'] is True
 assert '>' not in a['text']
 assert a['text'].count('?')==1
def test_plan_for_unverified_procedure_is_binding():
 p=ConversationPlanner().build(d(),ConversationState(),{})
 assert p.strategy=='clarify_then_guide' and not p.exact_operational_details_allowed
