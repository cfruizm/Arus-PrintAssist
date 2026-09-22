from __future__ import annotations
from copy import deepcopy
from .models import ConversationMemory,TurnUnderstanding
from .reconciler import TurnReconciler
from .memory import apply_understanding

def process_deterministic(message,semantic,store):
    memory=store["memory"];before=deepcopy(memory.to_dict())
    payload={"user_act":"new_request","intent":"unknown","topic_relation":"same_topic","domain_relevance":"in_scope","current_goal":"","goal_complete":False,"goal_updates":{},"case_updates":[],"needs_clarification":False,"clarification_target":None,"should_retrieve":False,"confidence":1.0,"reasoning_summary":"deterministic","degraded":False}
    payload.update(dict(semantic or {}))
    u=TurnUnderstanding(**payload);u,fixes=TurnReconciler().reconcile(u,memory,str(message));decision=TurnReconciler().decision(u,memory);apply_understanding(memory,u)
    answer={"text":"Deterministic contract evaluated without LLM.","mode":"deterministic","knowledge_used":False,"provider":None,"model":None,"usage":{"total_tokens":0},"finish_reason":"stop"}
    return {"input":message,"state_before":before,"understanding":u.to_dict(),"decision":decision,"answer":answer,"retrieval":{"enabled":False,"llm_called":False,"production_state_changed":False},"warnings":fixes,"validated_without_llm":True,"tokens_estimate":0,"production_changed":False,"state_after":deepcopy(memory.to_dict())}
