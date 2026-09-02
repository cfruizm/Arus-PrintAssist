from __future__ import annotations
from copy import deepcopy
from .models import ConversationState,EntityRef,Attempt

def norm(value):return " ".join(str(value or "").casefold().split())
def unique_append(values:list[str],value:str):
    value=" ".join(str(value or "").split())
    if value and not any(norm(x)==norm(value) for x in values):values.append(value);return True
    return False
def unique_entity(values:list[EntityRef],entity:EntityRef):
    if not any(x.kind==entity.kind and x.canonical_id==entity.canonical_id for x in values):values.append(entity);return True
    return False

def snapshot(state:ConversationState):return deepcopy(state.to_dict())
def archive_topic(state:ConversationState):
    if state.active_topic.products or state.technical_case.symptoms or state.technical_case.attempts:
        state.topic_history.append({"topic":deepcopy(state.active_topic),"case":deepcopy(state.technical_case)})
def reset_active_topic(state:ConversationState,new_id:str):
    from .models import TopicState,TechnicalCase
    archive_topic(state);state.active_topic=TopicState(topic_id=new_id);state.technical_case=TechnicalCase()
def cancel_all(state:ConversationState):
    from .models import TopicState,TechnicalCase,EscalationState
    state.active_topic=TopicState(topic_id=f"topic-{state.turn_number+1}");state.technical_case=TechnicalCase();state.escalation=EscalationState(status="cancelled");state.topic_history=[];state.last_action="cancel_all"
