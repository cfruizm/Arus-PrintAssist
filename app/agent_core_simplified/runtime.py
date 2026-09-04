from __future__ import annotations
import importlib,re
from .models import *
from .planner import Planner
from .state_engine import apply_plan
from .retrieval import build_query,prepare_candidates
from .composer import Composer
class SimplifiedAgentRuntime:
 def __init__(self,gateway,retriever,registry_module="app.domain_registry",max_candidates=5):
  self.gateway=gateway;self.retriever=retriever;self.planner=Planner(gateway);self.composer=Composer(gateway);self.max_candidates=max_candidates
  try:self.registry=importlib.import_module(registry_module)
  except Exception:self.registry=None
 def resolve(self,proposed):
  out=[]
  for x in proposed:
   kind=x.get("kind","product");name=x.get("name","");mention=x.get("mention",name);cid=x.get("canonical_id") or re.sub(r"[^a-z0-9]+","_",name.casefold()).strip("_")
   # Registry is authoritative when it exposes alias indexes; no product rules here.
   if self.registry:
    idx=getattr(self.registry,{"product":"PRODUCT_ALIAS_INDEX","component":"COMPONENT_ALIAS_INDEX","process":"PROCESS_ALIAS_INDEX"}.get(kind,""),{})
    if isinstance(idx,dict):
     for alias,target in sorted(idx.items(),key=lambda z:len(str(z[0])),reverse=True):
      if str(alias).casefold()==str(mention).casefold() or str(alias).casefold()==str(name).casefold():
       cid=str(target.get("canonical_id") if isinstance(target,dict) else target);name=str(target.get("canonical_name") if isinstance(target,dict) and target.get("canonical_name") else name);break
   out.append(Entity(kind,cid,name,mention,float(x.get("confidence",0))))
  return out
 def process(self,message,state):
  before=state.to_dict();plan=self.planner.plan(message,state);audit=apply_plan(state,plan,self.resolve);query="";candidates=[];answer={};calls_expected=1
  if plan.request_kind=="cancel":state.escalation.status="cancelled";answer={"answer":"Entendido. Cerré la gestión actual.","source_usage":[],"internal_knowledge_used":False,"limitations":[],"next_action":"Puedes iniciar una nueva consulta.","escalation_ready":False,"mode":"deterministic"}
  elif plan.request_kind=="out_of_scope":answer=self.composer.fallback(state,plan,[],"out_of_scope")
  elif plan.escalation_action in {"start","continue","finish"} or plan.request_kind=="escalate":answer={"answer":self.composer.escalation_summary(state),"source_usage":[],"internal_knowledge_used":False,"limitations":[],"next_action":"Completar los datos faltantes.","escalation_ready":True,"mode":"deterministic_escalation"}
  elif plan.needs_documents:
   query=build_query(message,state,plan);raw=self.retriever(query,self.max_candidates) or [];candidates=prepare_candidates(raw,self.max_candidates);answer=self.composer.compose(query,state,plan,candidates);calls_expected=2
  elif plan.request_kind=="none":
   answer={"answer":"Entendido. Incorporé esa información al caso y la tendré en cuenta en el siguiente paso.","source_usage":[],"internal_knowledge_used":False,"limitations":[],"next_action":"Continúa con el resultado observado o solicita la siguiente validación.","escalation_ready":bool(state.case.symptoms),"mode":"deterministic_ack"}
  else:answer=self.composer.compose(build_query(message,state,plan),state,plan,[]);calls_expected=2
  return {"input":message,"state_before":before,"plan":plan.to_dict(),"audit":audit,"retrieval_query":query,"candidates":candidates,"answer":answer,"state_after":state.to_dict(),"metrics":{"llm_calls_expected":calls_expected,"judge_calls":0,"repair_calls":0,"expansion_calls":0},"production_changed":False}
