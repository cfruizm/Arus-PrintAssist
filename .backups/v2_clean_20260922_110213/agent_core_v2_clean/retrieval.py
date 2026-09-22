from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib,json

@dataclass
class RetrievalQuery:
    text:str;fields:dict;fingerprint:str
    def to_dict(self):return asdict(self)

class RetrievalQueryBuilder:
    def build(self,message,memory,understanding):
        fields={"goal":memory.pending_goal.summary or understanding.current_goal,"intent":understanding.intent,"details":dict(memory.pending_goal.known_details),"symptoms":list(memory.support_case.symptoms),"observations":list(memory.support_case.observations[-4:]),"affected_scope":memory.support_case.affected_scope,"current_message":message,"topic_relation":understanding.topic_relation}
        parts=[str(fields.get("goal") or ""),str(message or "")]
        parts += [str(v) for v in fields["details"].values()]
        parts += fields["symptoms"]+fields["observations"]
        if fields["affected_scope"]:parts.append("alcance: "+str(fields["affected_scope"]))
        text=". ".join(dict.fromkeys(x.strip() for x in parts if x.strip()))[:1400]
        fp=hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
        return RetrievalQuery(text,fields,fp)
    def current_only(self,message,understanding):
        fields={"goal":understanding.current_goal,"intent":understanding.intent,"details":dict(understanding.goal_updates),"current_message":message}
        text=". ".join([str(understanding.current_goal or ""),str(message or "")] + [str(v) for v in fields["details"].values()])[:1000]
        return RetrievalQuery(text,fields,hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20])

class ReadOnlyRetrieval:
    def __init__(self,k=6):self.k=max(1,min(10,int(k)))
    def search(self,query,current_only=None):
        try:
            from app.integration.lab_retrieval_adapter import retrieve_from_existing_backend
            raw=retrieve_from_existing_backend(query.text,self.k)
        except Exception as exc:
            return {"enabled":True,"ok":False,"evidence":[],"count":0,"llm_called":False,"production_state_changed":False,"error_code":"adapter_error","errors":[f"{type(exc).__name__}: {exc}"]}
        raw["query"]=query.to_dict();raw["current_only_query"]=current_only.to_dict() if current_only else None
        raw["enabled"]=True;raw["production_state_changed"]=False
        return raw

def retrieval_summary(r):
    if not r or not r.get("ok"):return "No pude consultar la documentación en este turno. Conservé el contexto sin inventar un procedimiento."
    return f"Consulté la documentación y encontré {int(r.get('count',0))} fuente(s) candidatas para este turno."
