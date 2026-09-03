from .models import Attempt
from .state import *
class TransitionEngine:
 def apply(self,s,d):
  s.turn_number+=1;a={"applied":[],"skipped":[]}
  if d.action=="cancel_all":cancel(s);a["applied"].append("cancel_all");return a
  if d.topic_relation=="new_topic":new_topic(s);a["applied"].append("new_topic")
  if d.action=="start_escalation":s.escalation.status="collecting";a["applied"].append("start_escalation")
  elif d.action=="suspend_escalation":s.escalation.status="suspended";s.escalation.suspended_reason="independent_question";a["applied"].append("suspend")
  elif d.action=="resume_escalation":s.escalation.status="collecting";s.escalation.suspended_reason=None;a["applied"].append("resume")
  for e in d.entities:
   if e.kind not in {"product","component","process"}:a["skipped"].append("unsupported_entity:"+e.kind);continue
   xs=s.active_topic.products if e.kind=="product" else s.active_topic.components if e.kind=="component" else s.active_topic.processes
   (a["applied"] if add_entity(xs,e) else a["skipped"]).append("entity:"+e.canonical_id)
  for f in d.facts:
   t=str(f.get("type") or "");v=str(f.get("value") or "").strip()
   if t=="symptom" and v:
    if not any(norm(x)==norm(v) for x in s.technical_case.symptoms):s.technical_case.symptoms.append(v);a["applied"].append("symptom")
    s.technical_case.status="diagnosing"
   elif t=="affected_scope" and v:s.technical_case.affected_scope=v;s.technical_case.status="diagnosing";a["applied"].append("affected_scope")
   elif t=="attempted_action" and v:
    if not any(norm(x.action)==norm(v) for x in s.technical_case.attempts):s.technical_case.attempts.append(Attempt(v,None,s.turn_number));a["applied"].append(t)
   elif t=="attempt_result" and s.technical_case.attempts:
    last=s.technical_case.attempts[-1]
    if norm(last.result)!=norm(v):last.result=v;s.technical_case.status=s.technical_case.resolution_status="resolved" if norm(v) in {"resolved","successful"} else "unresolved";a["applied"].append(t)
   elif t=="evidence" and v and not any(norm(x)==norm(v) for x in s.technical_case.evidence):s.technical_case.evidence.append(v);a["applied"].append(t)
   elif t=="technical_context":a["skipped"].append("unmapped_technical_context")
  s.active_topic.intent=d.intent;s.last_action=d.action;return a
