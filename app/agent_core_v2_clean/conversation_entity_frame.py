from copy import deepcopy
def c(v):return " ".join(str(v or "").split()).strip()
def same(a,b):return c(a).casefold()==c(b).casefold()
def reconcile_entity_frame(memory,u):
 old=c(getattr(memory,"active_subject",None)) or None;new=c(getattr(u,"canonical_subject",None)) or None;origin=c(getattr(u,"subject_origin",None));ref=c(getattr(u,"reference_relation",None)) or "none";h=list(getattr(memory,"subject_history",[]) or []);selected=old;transition="inherit"
 if ref=="previous_subject" and h:
  selected=c(h[-1].get("subject")) or old;transition="return_to_previous"
  if old and selected and not same(old,selected):h[-1]={"subject":old,"turn":getattr(memory,"turn_number",0)}
 elif new and origin=="current_message":
  selected=new
  if old and not same(old,new):
   if not h or not same(h[-1].get("subject"),old):h.append({"subject":old,"turn":getattr(memory,"turn_number",0)})
   transition="explicit_subject_change"
 elif new:selected=new
 if selected:
  memory.active_subject=selected;u.canonical_subject=selected;u.goal_updates={**dict(getattr(u,"goal_updates",{}) or {}),"subject":selected}
 if transition=="explicit_subject_change":u.topic_relation="new_topic";u.user_act="new_request"
 elif transition=="return_to_previous":u.topic_relation="return_to_previous"
 memory.subject_history=h[-8:]
 return u,{"version":"entity_frame_v1","active_before":old,"explicit":new,"reference":ref,"selected":selected,"transition":transition,"history":deepcopy(memory.subject_history)}
