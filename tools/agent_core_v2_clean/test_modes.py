from app.agent_core_v2_clean.budget import BudgetPolicy
from app.agent_core_v2_clean.scenario_runner import run_all
def test_modes_have_expected_budgets():
 assert BudgetPolicy.for_mode('normal').understanding_max_tokens==300
 assert BudgetPolicy.for_mode('economy').understanding_max_tokens==180
 assert BudgetPolicy.for_mode('deterministic').max_session_calls==0
def test_deterministic_suite_is_effective_and_zero_cost():
 r=run_all();assert len(r)>=4 and all(x['passed'] for x in r)
 assert sum(x['llm_calls'] for x in r)==0 and sum(x['tokens'] for x in r)==0
def test_no_paused_mode():
 assert all(BudgetPolicy.for_mode(x).mode!='paused' for x in ('normal','economy','deterministic'))
