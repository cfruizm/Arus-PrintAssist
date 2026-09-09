from dataclasses import dataclass,asdict
@dataclass
class BudgetPolicy:
 mode:str="normal"
 max_session_calls:int=16
 max_session_tokens:int=9000
 reserve_tokens:int=900
 understanding_max_tokens:int=300
 response_max_tokens:int=220
 def to_dict(self):return asdict(self)
 @classmethod
 def for_mode(cls,mode):
  if mode=="economy":return cls("economy",8,4000,700,180,120)
  if mode=="deterministic":return cls("deterministic",0,0,0,0,0)
  return cls("normal",16,9000,900,300,220)
 def can_call(self,telemetry,estimated_tokens=650):
  if self.mode=="deterministic":return False,"deterministic_mode"
  if telemetry.get("last_rate_limit") is not None:return False,"provider_rate_limit"
  if telemetry.get("calls",0)>=self.max_session_calls:return False,"session_call_budget"
  if telemetry.get("total_tokens",0)+estimated_tokens+self.reserve_tokens>self.max_session_tokens:return False,"session_token_budget"
  return True,"allowed"
