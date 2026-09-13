from __future__ import annotations

def reconcile_turn(understanding, memory, message):
    """Conservative structural reconciliation. It never converts an explicit new topic to same topic."""
    corrections=[]
    has_anchor=bool(getattr(memory,'active_topic',None) or getattr(memory,'last_assistant_question',None))
    if understanding.user_act=='request_elaboration' and not has_anchor:
        understanding.user_act='new_request';understanding.topic_relation='new_topic';corrections.append('orphan_elaboration_to_new_request')
    if understanding.topic_relation=='new_topic':
        # Preserve the model's semantic decision. Post-processing may only repair impossible structures.
        pass
    if understanding.domain_relevance=='out_of_scope' and understanding.needs_clarification and understanding.clarification_target:
        understanding.domain_relevance='uncertain';understanding.should_retrieve=False;corrections.append('resolvable_scope_uncertainty')
    return understanding,corrections
