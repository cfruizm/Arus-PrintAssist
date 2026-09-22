from app.agent_core_v2_clean.robustness_gate import default_cases,run_gate,build_regression_contracts
class A:
 def __init__(self,d):self.d=d
 def to_dict(self):return self.d
def compliant(r):
 e=r.get('evidence') or [];x=r.get('procedural_expansion') or {};same=bool(x.get('same_document_only'));ordered=bool(x.get('ordered'));action=[]
 for item in e:
  t=(item.get('text') or '').lower()
  if any(v in t for v in ('open','verify','save','run','select','copy','execute','update','confirm')):action.append(item)
 pages={str(i.get('page')) for i in action if i.get('page')}
 if not r.get('ok') or not e or not action:status='insufficient'
 elif same and ordered and len(action)>=2 and len(pages)>=2:status='sufficient'
 else:status='partial'
 if not same or not ordered:status='partial' if action else 'insufficient'
 return A({'status':status,'score':1.0 if status=='sufficient' else .5 if status=='partial' else 0.0,'reasons':[],'usable_chunks':len(action),'unique_pages':len(pages),'same_document_only':same,'ordered':ordered,'generation_allowed':status=='sufficient','internal_knowledge_candidate':status!='sufficient'})
def test_full_controlled_matrix_passes():
 r=run_gate(compliant);assert r['approved'] and r['passed']==6 and r['llm_calls']==0
def test_gate_detects_regression():
 r=run_gate(lambda x:A({'status':'sufficient','generation_allowed':True,'internal_knowledge_candidate':False,'same_document_only':True,'ordered':True}));assert not r['approved'] and r['failed']>0
def test_cases_cover_boundaries():
 ids={x.case_id for x in default_cases()};assert ids=={'S01','P01','I01','I02','M01','O01'}
def test_regression_contracts_cover_prior_paths():
 ids={x['id'] for x in build_regression_contracts()['contracts']};assert {'R-CONCEPTUAL','R-PROCEDURAL','R-TOPIC','R-FOLLOWUP','R-DEGRADED'}<=ids
def test_no_product_or_benchmark_overfit():
 from pathlib import Path
 s=Path('app/agent_core_v2_clean/robustness_gate.py').read_text().casefold()
 for word in ('papercut','web jetadmin','template_fac','pre-facturasimp','facturación'):assert word not in s
