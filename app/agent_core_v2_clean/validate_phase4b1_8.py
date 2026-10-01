import inspect,json
from .documented_answer import DocumentedAnswerComposer,coverage_scope

class Result:
 def __init__(self,text):
  self.ok=True;self.text=text;self.provider='fixture';self.model='fixture';self.usage={'prompt_tokens':10,'completion_tokens':10,'total_tokens':20};self.finish_reason='stop'
 def to_dict(self):return {'ok':True,'text':self.text,'provider':self.provider,'model':self.model,'usage':self.usage,'finish_reason':self.finish_reason}
class Gateway:
 def __init__(self,text):self.text=text;self.calls=[]
 def complete(self,request):self.calls.append(request);return Result(self.text)

def run():
 evidence=[{'id':'R1','title':'Generic requirements','source':'/generic.pdf','page':'1','text':'A supported requirement has value 2026 and version 28. A comparable record uses 443 TCP.'}]
 retrieval={'evidence_verdict':{'accepted':True,'selected_evidence':evidence},'generation_evidence':evidence,'evidence':evidence}
 understanding={'intent':'requirements','user_act':'request_elaboration','topic_relation':'same_topic','current_goal':'Review requirements','goal_updates':{}}
 gateway=Gateway('La documentación confirma el requisito respaldado [R1].')
 composer=DocumentedAnswerComposer(gateway,760)
 answer=composer.compose('Resume las consideraciones documentadas',understanding,retrieval)
 source=inspect.getsource(__import__('app.agent_core_v2_clean.documented_answer',fromlist=['x']))
 scope=coverage_scope('Resume las consideraciones documentadas',understanding,evidence)
 exhaustive=coverage_scope('Lista completa de todos los requisitos',understanding,evidence)
 checks={
  'single_generation_call':len(gateway.calls)==1,
  'no_numeric_fact_extraction':scope['fact_extraction_used'] is False,
  'no_automatic_repair':scope['automatic_repair_allowed'] is False and composer.validation['coverage_repair']['attempted'] is False,
  'numbers_do_not_trigger_partial':answer.mode=='documented_answer' and answer.finish_reason=='stop',
  'explicit_exhaustiveness_observed_only':exhaustive['exhaustive_requested'] is True,
  'no_coverage_repair_provider_purpose':'documented_answer_coverage_repair' not in source,
  'no_fixed_products_or_values':all(x not in source.casefold() for x in ['hp sds monitor','papercut mf','port 443','puerto 443']),
  'validation_remains_exportable':'coverage_scope' in composer.validation and 'requested_dimension_coverage' in composer.validation,
 }
 failed=[k for k,v in checks.items() if not v]
 return {'phase':'4B.1.8','passed':len(checks)-len(failed),'failed':len(failed),'checks':checks}
if __name__=='__main__':
 result=run();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(1 if result['failed'] else 0)
