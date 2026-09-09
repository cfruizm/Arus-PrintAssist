from __future__ import annotations
from dataclasses import dataclass,asdict

@dataclass(frozen=True)
class BudgetPolicy:
    mode:str="normal"
    max_session_calls:int=24
    max_session_tokens:int=14000
    reserve_tokens:int=1200
    understanding_max_tokens:int=300
    response_max_tokens:int=220
    @classmethod
    def for_mode(cls,mode:str):
        value=str(mode or "normal").strip().casefold()
        if value=="economy":return cls("economy",12,7000,900,180,120)
        if value=="deterministic":return cls("deterministic",0,0,0,0,0)
        return cls("normal",24,14000,1200,300,220)
    def to_dict(self):return asdict(self)
    def can_call(self,telemetry,estimated_tokens:int=0):
        if self.mode=="deterministic":return False,"deterministic_mode"
        calls=int((telemetry or {}).get("calls",0));tokens=int((telemetry or {}).get("total_tokens",0));estimate=max(0,int(estimated_tokens or 0))
        if calls>=self.max_session_calls:return False,"session_call_budget_exhausted"
        usable=max(0,self.max_session_tokens-self.reserve_tokens)
        if tokens+estimate>usable:return False,"session_token_budget_would_exceed_reserve"
        return True,None
