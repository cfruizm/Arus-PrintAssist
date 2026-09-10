from types import SimpleNamespace
from app.agent_core_v2_clean.semantic_fit import evaluate_item
from app.agent_core_v2_clean.semantic_contract import validate_response_contract

def test_no_closed_domain_vocabulary():
 import app.agent_core_v2_clean.semantic_fit as m
 s=open(m.__file__,encoding='utf-8').read().casefold()
 for token in ('papercut','mfpsecure','authentication":{"','conceptual_cues','procedural_cues','concept:cost'):assert token not in s
def test_generic_overlap_works_for_unseen_domain():
 x=evaluate_item({'title':'Quantum relay calibration','text':'calibrate quantum relay safely'},'quantum relay calibration',{'goal':'quantum relay calibration'},{});assert x['score']>0
def test_confirmed_fact_contradiction_detected_without_product_rule():
 c={'confirmed_facts':[{'key':'component','value':'Orion','status':'confirmed'}]};v=validate_response_contract('La plataforma no se ha confirmado.',c);assert not v['valid']
