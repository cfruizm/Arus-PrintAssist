from .response_planner import build_response_plan,apply_plan
def plan_turn(result,message):
 u=dict(result.get('understanding') or {})
 frame=result.get('canonical_conversation_frame') or {}
 subject=(frame.get('subject') or {}).get('value')
 operation=(frame.get('operation') or {}).get('text')
 if subject or operation:
  details=dict(u.get('goal_updates') or {})
  if subject: details['subject']=subject
  if operation: details['operation']=operation
  u['goal_updates']=details
 p=build_response_plan(message,u,result.get('retrieval') or {},result.get('evidence_decision') or {})
 result['canonical_response_plan']=p.to_dict();result['retrieval']=apply_plan(result.get('retrieval') or {},p);return result,p
def assessment_from_plan(plan,base=None):
 out=dict(base or {});mode=plan.response_plan['mode'];status='sufficient' if mode=='documented' else 'partial' if mode in {'hybrid','general_guidance_with_example'} else 'insufficient';out.update({'status':status,'generation_allowed':mode=='documented','internal_knowledge_candidate':mode!='documented','reasons':list(dict.fromkeys([*(out.get('reasons') or []),'canonical_response_plan:'+mode]))});out['canonical_decision']={'status':status,'generation_mode':'documented' if mode=='documented' else 'documented_plus_internal' if mode=='hybrid' else 'internal_only','reason':'canonical_response_plan:'+mode,'selected_ids':plan.evidence_plan['documented_ids'],'accepted':mode=='documented'};return out
