from types import SimpleNamespace
from app.agent_core_v2_clean.conversational_authority import reconcile_understanding
from app.agent_core_v2_clean.diagnostic_progression import compact_diagnostic_progression
from app.agent_core_v2_clean.fallback_authority import fallback_matches_current_goal


def memory(active=True):
    return SimpleNamespace(
        active_topic='Active supported goal' if active else None,
        pending_goal=SimpleNamespace(summary='Active supported goal' if active else ''),
        last_assistant_question=None,
        support_case=SimpleNamespace(
            status='diagnosing', symptoms=['Observed failure'],
            observations=['Network path confirmed'],
            attempts=[{'action':'Restarted component','result':'Failure remains'}],
        ),
    )


def understanding(**changes):
    base=dict(user_act='request_elaboration', intent='troubleshooting',
              topic_relation='same_topic', domain_relevance='out_of_scope',
              should_retrieve=True)
    base.update(changes)
    return SimpleNamespace(**base)


def test_active_supported_continuation_overrides_false_out_of_scope():
    value, trace = reconcile_understanding(understanding(), memory())
    assert value.domain_relevance == 'in_scope'
    assert trace.scope_overridden is True
    assert 'continuation_of_active_in_scope_topic' in trace.reasons


def test_independent_out_of_scope_remains_out_of_scope():
    value, trace = reconcile_understanding(
        understanding(user_act='independent_question', intent='unknown', topic_relation='independent'),
        memory(),
    )
    assert value.domain_relevance == 'out_of_scope'
    assert trace.scope_overridden is False


def test_provider_new_topic_is_not_downgraded_by_elaboration_act():
    value, trace = reconcile_understanding(
        understanding(intent='procedural', topic_relation='new_topic', domain_relevance='in_scope'),
        memory(),
    )
    assert value.topic_relation == 'new_topic'
    assert value.user_act == 'new_request'
    assert 'provider_new_topic_preserved' in trace.reasons


def test_diagnostic_progression_exposes_prior_facts_and_results():
    payload = compact_diagnostic_progression(memory())
    assert payload['confirmed_observations'] == ['Network path confirmed']
    assert payload['attempted_actions'][0]['result'] == 'Failure remains'
    assert payload['response_policy']['do_not_request_confirmed_information'] is True


def test_new_topic_fallback_rejects_carried_evidence():
    result={'topic_boundary':{'relation':'new_topic'}}
    retrieval={'generation_evidence':[{'carried_from_previous_answer':True}],
               'semantic_fit':{'previous_answer_sources_used':True}}
    assert fallback_matches_current_goal(result,retrieval) is False
    assert result['fallback_authority']['reason']=='evidence_from_previous_goal'


def test_same_topic_fallback_can_use_current_evidence():
    result={'topic_boundary':{'relation':'same_topic_refinement'}}
    retrieval={'generation_evidence':[{'carried_from_previous_answer':False}],
               'semantic_fit':{'previous_answer_sources_used':False}}
    assert fallback_matches_current_goal(result,retrieval) is True
