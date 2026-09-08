from types import SimpleNamespace
from app.agent_core_v2.response import ResponseComposer
from app.agent_core_v2.models import ConversationState, CanonicalDecision, InterpreterProposal, EntityRef
from app.agent_core_v2.decision import DecisionReconciler

class Gateway:
    def __init__(self,text): self.text=text
    def complete(self,request):
        return SimpleNamespace(ok=True,text=self.text,provider="test",model="test",usage={},finish_reason="stop")

def decision(intent="procedural"):
    return CanonicalDecision("retrieve",intent,"technical_request","same_topic",[],[],None,.9,[],False,True)

def test_no_evidence_can_never_be_grounded():
    answer=ResponseComposer(Gateway("Orientación complementaria, no confirmada por las fuentes recuperadas: revisa primero el contexto y evita cambios no validados."),500).compose("consulta",decision(),ConversationState(),{"unassessed":[]})
    assert answer["mode"]=="guarded_internal_knowledge"
    assert answer["selected_evidence_ids"]==[]
    assert answer["citations"]==[]
    assert answer["internal_knowledge_used"] is True
    assert answer["internal_knowledge_warning_shown"] is True

def test_grounded_requires_citable_claims_and_citations():
    evidence={"direct":[{"id":"S1","title":"Documento","url":"https://example","citable":True,"semantic_assessment":{"applicability":"direct","supported_claims":["Afirmación respaldada"]}}]}
    answer=ResponseComposer(Gateway("Afirmación respaldada [S1]."),500).compose("consulta",decision("conceptual"),ConversationState(),evidence)
    assert answer["mode"]=="grounded"
    assert answer["selected_evidence_ids"]==["S1"]
    assert [x["id"] for x in answer["citations"]]==["S1"]

def test_new_same_topic_entity_is_persistable():
    state=ConversationState(); entity=EntityRef("process","generic_process","Proceso")
    proposal=InterpreterProposal("technical_request","procedural","retrieve","same_topic",[],[],None,.9,"semantic")
    result=DecisionReconciler().reconcile(proposal,state,[entity])
    assert result.state_mutation_allowed is True

def test_canonical_clarification_is_not_replaced_by_free_answer():
    d=CanonicalDecision("ask_clarification","unknown","clarification","same_topic",[],[],"Pregunta canónica",.4,[],False,False)
    answer=ResponseComposer(Gateway("respuesta libre"),500).compose_conversation("mensaje",d,ConversationState())
    assert answer["mode"]=="clarification"
    assert answer["text"]=="Pregunta canónica"
