from __future__ import annotations
from typing import Any,Mapping
import hashlib,json

def _mapping(v):return dict(v) if isinstance(v,Mapping) else {}
def _text(v):return " ".join(str(v or "").split())
def _fingerprint(text,fields):
 payload=json.dumps({"text":text,"fields":fields},sort_keys=True,ensure_ascii=False,default=str,separators=(",",":"))
 return hashlib.sha256(payload.encode()).hexdigest()[:20]
def apply_canonical_query(query,frame):
 f=_mapping(frame);subject=_mapping(f.get("subject"));operation=_mapping(f.get("operation"));topic=_mapping(f.get("topic"));case=_mapping(f.get("case"))
 subject_value=_text(subject.get("value"));operation_text=_text(operation.get("text"));intent=_text(operation.get("intent"))
 fields=dict(getattr(query,"fields",{}) or {})
 if subject_value:
  fields.update({"subject":subject_value,"subject_type":_text(subject.get("type")),"subject_id":_text(subject.get("canonical_id")) or subject_value})
 if intent and intent!="unknown":fields["intent"]=intent
 fields.update({"operation":operation_text,"topic_id":_text(topic.get("topic_id")),"topic_relation":_text(topic.get("relation")),"canonical_query":True})
 if case.get("symptoms"):fields["symptoms"]=list(case.get("symptoms") or [])
 if case.get("observations"):fields["observations"]=list(case.get("observations") or [])
 if case.get("affected_scope"):fields["affected_scope"]=case.get("affected_scope")
 parts=[]
 for value in (subject_value,operation_text):
  if value and value.casefold() not in {x.casefold() for x in parts}:parts.append(value)
 text=". ".join(parts) or _text(getattr(query,"text",""))
 query.text=text;query.fields=fields;query.fingerprint=_fingerprint(text,fields);return query
