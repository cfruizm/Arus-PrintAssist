from dataclasses import dataclass,asdict

@dataclass
class ConversationPlan:
 strategy:str
 answer_first:bool=True
 ask_one_question:bool=False
 question_goal:str|None=None
 evidence_level:str="none"
 allow_general_knowledge:bool=True
 visible_disclosure:str="light"
 def to_dict(self):return asdict(self)

class ConversationPlanner:
 def build(self,decision,state,evidence=None):
  evidence=evidence or {};direct=bool(evidence.get("direct"));bounded=bool((evidence.get("partial") or [])+(evidence.get("conditional") or []))
  level="direct" if direct else "bounded" if bounded else "none"
  if decision.action=="decline_out_of_scope":return ConversationPlan("redirect_scope",True,False,None,level,False,"none")
  if decision.action=="ask_clarification":return ConversationPlan("clarify",False,True,"resolve the current ambiguity using active context",level,False,"none")
  if decision.intent=="troubleshooting":return ConversationPlan("diagnose",True,True,"identify the next missing diagnostic fact",level,True,"light")
  if decision.intent=="procedural" and level=="none":return ConversationPlan("clarify_then_guide",True,True,"identify the exact operation, object or environment needed for safe guidance",level,True,"light")
  return ConversationPlan("answer",True,False,None,level,True,"light")
