from dataclasses import dataclass,asdict
@dataclass(frozen=True)
class BudgetPolicy:
    mode:str="normal";max_session_calls:int=20;max_session_tokens:int=12000;reserve_tokens:int=700;understanding_max_tokens:int=320;response_max_tokens:int=280
    @classmethod
    def for_mode(cls,mode):
        m=str(mode or "normal").casefold()
        if m=="economy":return cls("economy",8,5000,400,260,180)
        if m=="deterministic":return cls("deterministic",0,0,0,0,0)
        return cls()
    def to_dict(self):return asdict(self)
