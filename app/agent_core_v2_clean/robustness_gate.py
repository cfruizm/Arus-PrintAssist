from __future__ import annotations
from dataclasses import dataclass,asdict
from typing import Callable,Any
import copy,json

GATE_VERSION='phase2d2_robustness_v1'

@dataclass(frozen=True)
class GateCase:
    case_id:str
    category:str
    description:str
    expected:dict[str,Any]
    retrieval:dict[str,Any]

@dataclass(frozen=True)
class GateResult:
    case_id:str
    category:str
    passed:bool
    expected:dict[str,Any]
    observed:dict[str,Any]
    mismatches:list[str]
    def to_dict(self):return asdict(self)

def _e(page,text,source='doc-a'):
    return {'id':f'R{page}','page':str(page),'source':source,'url':source,'title':'Controlled fixture','text':text,'metadata':{'page_label':str(page),'source':source}}

def default_cases()->list[GateCase]:
    """Controlled synthetic fixtures test contracts, never product names or benchmark phrases."""
    action_a=('Open the configuration file, verify the required field, save the change, run the process and confirm the result. ')*7
    action_b=('Select the next option, copy the validated values, execute the operation, update the view and verify completion. ')*7
    noise=('General notice, retention information, document control and administrative metadata without operational instructions. ')*7
    return [
      GateCase('S01','sufficiency','Multi-page actionable evidence in one ordered document',{'status':'sufficient','generation_allowed':True,'internal_knowledge_candidate':False},{'ok':True,'evidence':[_e(1,action_a),_e(2,action_b)],'document_groups':[{'identity':'doc-a','title':'Controlled fixture','pages':['1','2'],'chunks':2}],'procedural_expansion':{'ok':True,'same_document_only':True,'ordered':True,'pages':['1','2']}}),
      GateCase('P01','sufficiency','One actionable page is useful but incomplete',{'status':'partial','generation_allowed':False,'internal_knowledge_candidate':True},{'ok':True,'evidence':[_e(1,action_a)],'document_groups':[{'identity':'doc-a','title':'Controlled fixture','pages':['1'],'chunks':1}],'procedural_expansion':{'ok':True,'same_document_only':True,'ordered':True,'pages':['1']}}),
      GateCase('I01','sufficiency','No retrieved evidence',{'status':'insufficient','generation_allowed':False,'internal_knowledge_candidate':True},{'ok':True,'evidence':[],'document_groups':[],'procedural_expansion':{'ok':False,'same_document_only':False,'ordered':False,'pages':[]}}),
      GateCase('I02','sufficiency','Non-actionable administrative content',{'status':'insufficient','generation_allowed':False,'internal_knowledge_candidate':True},{'ok':True,'evidence':[_e(1,noise)],'document_groups':[{'identity':'doc-a','title':'Controlled fixture','pages':['1'],'chunks':1}],'procedural_expansion':{'ok':True,'same_document_only':True,'ordered':True,'pages':['1']}}),
      GateCase('M01','isolation','Actionable chunks from multiple documents',{'generation_allowed':False,'same_document_only':False},{'ok':True,'evidence':[_e(1,action_a,'doc-a'),_e(2,action_b,'doc-b')],'document_groups':[{'identity':'doc-a'},{'identity':'doc-b'}],'procedural_expansion':{'ok':True,'same_document_only':False,'ordered':True,'pages':['1','2']}}),
      GateCase('O01','ordering','Evidence explicitly marked unordered',{'generation_allowed':False,'ordered':False},{'ok':True,'evidence':[_e(2,action_b),_e(1,action_a)],'document_groups':[{'identity':'doc-a'}],'procedural_expansion':{'ok':True,'same_document_only':True,'ordered':False,'pages':['2','1']}}),
    ]

def _pick(assessment:dict)->dict:
    keys=('status','score','reasons','usable_chunks','unique_pages','same_document_only','ordered','generation_allowed','internal_knowledge_candidate')
    return {k:copy.deepcopy(assessment.get(k)) for k in keys if k in assessment}

def run_gate(assess_fn:Callable[[dict],Any],cases:list[GateCase]|None=None)->dict:
    results=[]
    for case in cases or default_cases():
        raw=assess_fn(copy.deepcopy(case.retrieval));assessment=raw.to_dict() if hasattr(raw,'to_dict') else dict(raw);observed=_pick(assessment);mismatches=[]
        for key,value in case.expected.items():
            if observed.get(key)!=value:mismatches.append(f'{key}: expected={value!r}, observed={observed.get(key)!r}')
        results.append(GateResult(case.case_id,case.category,not mismatches,case.expected,observed,mismatches))
    passed=sum(x.passed for x in results);total=len(results)
    return {'gate_version':GATE_VERSION,'synthetic_fixtures':True,'llm_calls':0,'production_changed':False,'passed':passed,'failed':total-passed,'total':total,'approved':passed==total,'results':[x.to_dict() for x in results]}

def build_regression_contracts()->dict:
    return {'gate_version':GATE_VERSION,'contracts':[
      {'id':'R-CONCEPTUAL','purpose':'Previously approved conceptual documented answer remains unchanged','required':['documented_answer','citations','readable_sources','goal_complete','final_cache_zero_tokens']},
      {'id':'R-PROCEDURAL','purpose':'Previously approved procedural answer remains complete and grounded','required':['single_document','ordered_evidence','sufficiency_gate','finish_reason_stop','valid_citations','goal_complete','final_cache_zero_tokens']},
      {'id':'R-TOPIC','purpose':'Context isolation across a topic change','required':['current_turn_query','no_previous_evidence_leak','cache_key_changes']},
      {'id':'R-FOLLOWUP','purpose':'Follow-up reuses relevant context without repeating unrelated content','required':['same_topic','relevant_memory','no_full_answer_repetition_unless_requested']},
      {'id':'R-DEGRADED','purpose':'Provider or budget degradation stays transparent and safe','required':['no_partial_answer_published','diagnostic_reason','zero_false_failures_on_cache']},
    ]}

def write_report(path:str,assess_fn:Callable[[dict],Any])->dict:
    report=run_gate(assess_fn);report['regression_contracts']=build_regression_contracts();
    with open(path,'w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    return report
