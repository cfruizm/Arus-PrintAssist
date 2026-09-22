from __future__ import annotations
from dataclasses import dataclass,asdict
@dataclass(frozen=True)
class ModelProfile:
 model:str;family:str="generic";understanding_mode:str="schema";schema_strict:bool=False;reasoning_effort:str|None=None;repair_once:bool=True;safe_output_tokens:int=620
 def to_dict(self):return asdict(self)
def profile_for(model):
 value=str(model or "").casefold()
 if "gpt-oss" in value:return ModelProfile(str(model or ""),"gpt_oss","text_json",False,"low",True,620)
 if "qwen" in value:return ModelProfile(str(model or ""),"qwen","schema",False,None,True,620)
 return ModelProfile(str(model or ""),"generic","schema",False,None,True,560)
def is_quota_error(result):
 if not result:return False
 data=result if isinstance(result,dict) else getattr(result,"to_dict",lambda:{})()
 text=" ".join(str(data.get(k) or "") for k in ("error_code","provider_error_code","error_message","message")).casefold()
 return "rate_limit" in text or "tokens per day" in text or "tpd" in text or "quota" in text
