from dataclasses import dataclass,asdict
@dataclass
class ConversationPlan:
 strategy:str;answer_first:bool=True;ask_one_question:bool=False;question_goal:str|None=None;evidence_level:str="none";allow_general_knowledge:bool=True;exact_operational_details_allowed:bool=False
 def to_dict(self):return asdict(self)
class ConversationPlanner:
 def build(self,d,state,e=None):
  e=e or {};direct=bool(e.get("direct"));bounded=bool((e.get("partial") or [])+(e.get("conditional") or []));level="direct" if direct else "bounded" if bounded else "none"
  if d.action=="decline_out_of_scope":return ConversationPlan("redirect_scope",True,False,None,level,False,False)
  if d.action=="ask_clarification":return ConversationPlan("clarify",False,True,"resolve only the necessary ambiguity",level,False,False)
  if d.intent=="troubleshooting":return ConversationPlan("diagnose",True,True,"obtain the most useful missing diagnostic fact",level,True,direct)
  if d.intent=="procedural" and not direct:return ConversationPlan("clarify_then_guide",True,True,"identify the exact operation or environment",level,True,False)
  return ConversationPlan("answer",True,False,None,level,True,direct)
