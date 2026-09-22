from agent_core_v2_clean_phase3b2_2_complete.models import ConversationMemory,TurnUnderstanding
from agent_core_v2_clean_phase3b2_2_complete.conversational_authority import reconcile_understanding
from agent_core_v2_clean_phase3b2_2_complete.memory import apply_understanding
from agent_core_v2_clean_phase3b2_2_complete.natural_recovery import recover_natural_response
from agent_core_v2_clean_phase3b2_2_complete.operation_requirements import derive_missing_details
from agent_core_v2_clean_phase3b2_2_complete.entity_scope import CanonicalScope

def run():
    m=ConversationMemory();m.active_topic='Diagnosticar cola';m.pending_goal.summary='Diagnosticar cola';m.pending_goal.intent='troubleshooting';m.pending_goal.status='active';m.support_case.status='diagnosing'
    u=TurnUnderstanding('request_elaboration','procedural','same_topic','out_of_scope','Obtener siguiente procedimiento',False,{},[],False,None,True,1.0,'fixture')
    u,t=reconcile_understanding(u,m);assert u.domain_relevance=='in_scope' and t.scope_overridden
    q=TurnUnderstanding('follow_up','troubleshooting','same_topic','in_scope','Diagnosticar cola',False,{'observations':'La cola aparece sin conexión'},[],False,None,True,1.0,'fixture')
    apply_understanding(m,q);assert 'La cola aparece sin conexión' in m.support_case.observations
    r={'answer':{'text':'Paso completo. Texto incompleto','mode':'natural_support','finish_reason':'length'},'provider_trace':{'response':{'text':'Paso completo. Texto incompleto'}}}
    recover_natural_response(r);assert r['answer']['mode']=='natural_compact_recovery' and 'Paso completo.' in r['answer']['text']
    missing=derive_missing_details('instalar cola compartida','cola de impresión',CanonicalScope());assert missing==['operating_system','architecture']
    print(json.dumps({'passed':4,'failed':0},ensure_ascii=False))
if __name__=='__main__':
    import json;run()
