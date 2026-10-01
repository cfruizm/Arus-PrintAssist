import json,sys
from pathlib import Path
from .models import ConversationMemory
from .understanding import ConversationUnderstanding
class Result:
 def __init__(self,text):self.ok=True;self.text=text;self.error_code=None
 def to_dict(self):return {"ok":True,"text":self.text}
class Gateway:
 def __init__(self,text):self.text=text;self.calls=0
 def complete(self,request):self.calls+=1;return Result(self.text)
def run(path):
 data=json.loads(Path(path).read_text(encoding='utf-8'))
 turn=next(t for t in data['turns'] if t['input'].casefold().strip()=='gracias' and t['state_before'].get('active_subject'))
 raw=turn['provider_trace']['understanding']['text']
 g=Gateway(raw);e=ConversationUnderstanding(g,220)
 m=ConversationMemory(active_topic=turn['state_before']['active_topic'],active_subject=turn['state_before']['active_subject'])
 u=e.interpret(turn['input'],m)
 checks={
  'runtime_contract_social':u.user_act=='social' and u.intent=='social',
  'retrieval_disabled':u.should_retrieve is False,
  'inherited_subject_not_new_work':u.canonical_subject is None and u.reference_relation=='none',
  'provider_status_preserved_for_normalization':e.normalization.get('provider_goal_status') in {'complete','completed','closed'},
  'closure_correction_precedes_followup':'semantic_non_operational_closure_recovered_before_followup_policy' in e.normalization.get('structural_corrections',[]),
  'generic_followup_rewrite_not_applied':'answer_without_pending_question_normalized' not in e.normalization.get('structural_corrections',[]),
  'single_understanding_call':g.calls==1,
  'no_literal_message_rule':'gracias' not in Path(__file__).with_name('understanding.py').read_text(encoding='utf-8').casefold(),
 }
 failed=[k for k,v in checks.items() if not v]
 return {'phase':'4B.1.10','passed':len(checks)-len(failed),'failed':len(failed),'checks':checks,'normalized':u.to_dict(),'normalization':e.normalization}
if __name__=='__main__':
 r=run(sys.argv[1]);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(1 if r['failed'] else 0)
