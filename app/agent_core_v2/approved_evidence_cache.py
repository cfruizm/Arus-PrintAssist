from __future__ import annotations
from copy import deepcopy
from typing import Any

def make_snapshot(*, topic: dict[str,Any], intent: str, selection: dict[str,Any], coverage: dict[str,Any] | None=None, complete_enough: bool=False):
 return {"topic_id":topic.get("topic_id"),"intent":intent,"products":deepcopy(topic.get("products") or []),"components":deepcopy(topic.get("components") or []),"selection":deepcopy(selection),"coverage":deepcopy(coverage or {}),"complete_enough":bool(complete_enough)}

def snapshot_matches(snapshot: dict[str,Any] | None, topic: dict[str,Any], intent: str | None=None) -> bool:
 if not snapshot:return False
 if snapshot.get("topic_id") != topic.get("topic_id"):return False
 return intent is None or snapshot.get("intent") == intent
