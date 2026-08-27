from __future__ import annotations
from dataclasses import dataclass,field,asdict
from typing import Any

@dataclass
class LLMRequest:
    messages:list[dict[str,str]]
    purpose:str="diagnostic"
    max_tokens:int=180
    temperature:float=0.0
    response_schema:dict[str,Any]|None=None

@dataclass
class LLMResult:
    ok:bool
    text:str=""
    provider:str=""
    model:str=""
    purpose:str=""
    latency_ms:float=0.0
    usage:dict[str,int]=field(default_factory=dict)
    finish_reason:str|None=None
    error_code:str|None=None
    error_message:str|None=None
    fallback_used:bool=False
    fallback_provider:str|None=None
    metadata:dict[str,Any]=field(default_factory=dict)
    def to_dict(self):return asdict(self)
