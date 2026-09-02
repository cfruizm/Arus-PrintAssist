from copy import deepcopy
from .models import *
def norm(v):return " ".join(str(v or "").casefold().split())
def snapshot(s):return deepcopy(s.to_dict())
def add_entity(xs,e):
 if any(x.kind==e.kind and x.canonical_id==e.canonical_id for x in xs):return False
 xs.append(e);return True
def archive(s):
 if s.active_topic.products or s.technical_case.symptoms or s.technical_case.attempts:s.topic_history.append({"topic":deepcopy(s.active_topic),"case":deepcopy(s.technical_case)})
def new_topic(s):archive(s);s.active_topic=TopicState(f"topic-{s.turn_number}");s.technical_case=TechnicalCase()
def cancel(s):s.active_topic=TopicState(f"topic-{s.turn_number}");s.technical_case=TechnicalCase();s.escalation=EscalationState(status="cancelled");s.topic_history=[]
