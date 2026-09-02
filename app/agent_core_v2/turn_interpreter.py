from __future__ import annotations
from typing import Protocol
from .models import InterpreterProposal,ConversationState

class Interpreter(Protocol):
    def interpret(self,message:str,state:ConversationState)->InterpreterProposal:...

class StructuredInterpreter:
    """Adapter for a callable returning the semantic JSON contract."""
    def __init__(self,callable_):self.callable=callable_
    def interpret(self,message,state):
        raw=self.callable(message,state.to_dict())
        return InterpreterProposal(**raw)

class ScriptedInterpreter:
    """Offline benchmark interpreter. Production LLM integration belongs to phase 2."""
    def __init__(self,outputs):self.outputs=list(outputs);self.index=0
    def interpret(self,message,state):
        raw=self.outputs[self.index];self.index+=1
        return InterpreterProposal(**raw)
