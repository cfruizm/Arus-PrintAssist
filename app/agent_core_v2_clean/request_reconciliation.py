from __future__ import annotations
import re,unicodedata
_CORRECTION=("me refiero","queria decir","quise decir","documento correcto","fuente correcta","especificamente","en realidad")
_NEGATIVE=[re.compile(r"\b(?:no quiero (?:usar|utilizar)|sin utilizar|sin usar|no utilizar|no usar|que no sea|no mediante|excepto|sin)\s+(.+?)(?:[.,;!?]|$)",re.I)]
def norm(v):return unicodedata.normalize("NFKD",str(v or "")).encode("ascii","ignore").decode().casefold().strip()
def negative_constraints(message):
 out=[]
 for rx in _NEGATIVE:
  for value in rx.findall(str(message or "")):
   value=" ".join(value.strip().split())
   if value and value.casefold() not in {x.casefold() for x in out}:out.append(value)
 return out
def reconcile(message,understanding,state_before):
 u=dict(understanding or {});pending=(state_before or {}).get("pending_goal") or {};old_goal=str(pending.get("summary") or "");text=norm(message)
 correction=any(x in text for x in _CORRECTION)
 details=dict(u.get("goal_updates") or {})
 subject=str(u.get("canonical_subject") or details.get("subject") or "")
 if correction and old_goal and subject:
  u["current_goal"]=old_goal+". Usar como sujeto o fuente corregida: "+subject
  u["topic_relation"]="same_topic"
  u["reference_relation"]="corrected_subject"
  u["subject_origin"]="current_message"
 constraints=negative_constraints(message)
 if constraints:
  u["negative_constraints"]=constraints
  u["current_goal"]=(str(u.get("current_goal") or old_goal or message)+". Excluir: "+"; ".join(constraints)).strip()
  u["topic_relation"]="same_topic"
  u["reference_relation"]="negative_constraint"
 return u,{"correction_detected":correction,"preserved_previous_operation":bool(correction and old_goal),"negative_constraints":constraints}
def filter_excluded(items,constraints):
 if not constraints:return list(items or []),[]
 kept=[];rejected=[]
 for item in items or []:
  hay=norm(" ".join(str(x or "") for x in (item.get("title"),item.get("source"),item.get("url"))))
  if any(norm(c) and norm(c) in hay for c in constraints):rejected.append(item)
  else:kept.append(item)
 return kept,rejected
