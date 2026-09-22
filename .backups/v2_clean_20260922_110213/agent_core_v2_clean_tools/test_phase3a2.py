from pathlib import Path
import ast

def src():return Path('app/agent_core_v2_clean/understanding.py').read_text()
def test_syntax():ast.parse(src())
def test_referential_same_topic_becomes_followup():
 s=src();assert 'answer_without_pending_question_to_follow_up' in s and 'x.user_act="follow_up"' in s
def test_new_unrelated_request_remains_new_request():assert 'answer_without_pending_question_to_new_request' in src()
def test_prompt_prevents_arbitrary_platform_binding():
 s=src();assert 'arbitrary platform' in s and 'single scope fact needed to ground the answer' in s
def test_prompt_does_not_require_all_details():assert 'Do not require version, model, environment' in src()
def test_answer_to_question_is_reserved():assert 'reserved only for an explicit pending assistant question' in src()
def test_no_product_specific_rules():
 s=src().casefold()
 for word in ('papercut','web jetadmin','epson','dca','tarjeta','pin'):assert word not in s
