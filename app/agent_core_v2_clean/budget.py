from dataclasses import dataclass,asdict
@dataclass
class BudgetPolicy:
 mode:str="live_economy"
 max_session_calls:int=12
 max_session_tokens:int=6000
 max_turn_calls:int=2
 understanding_max_tokens:int=180
 response_max_tokens:int=120
 reserve_tokens:int=900
 def to_dict(self):return asdict(self)
 def can_call(self,telemetry,estimated_tokens=350):
  if self.mode=="dry_run":return False,"dry_run"
  if telemetry.get("calls",0)>=self.max_session_calls:return False,"session_call_budget"
  if telemetry.get("total_tokens",0)+estimated_tokens+self.reserve_tokens>self.max_session_tokens:return False,"session_token_budget"
  if telemetry.get("last_rate_limit") is not None:return False,"provider_rate_limit"
  return True,"allowed"
