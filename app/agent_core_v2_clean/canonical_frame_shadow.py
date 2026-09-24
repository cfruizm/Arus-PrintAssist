from __future__ import annotations
from copy import deepcopy
from .canonical_frame import build_frame,validate_frame

STORE_KEY="canonical_conversation_frame"


def build_shadow_frame(store: dict, message: str, result: dict)->dict:
    previous=deepcopy(store.get(STORE_KEY) or {})
    frame=build_frame(message,result.get("understanding") or {},result.get("state_before") or {},store.get("answer_context") or {},previous)
    payload=frame.to_dict();payload["validation"]={"valid":not validate_frame(frame),"issues":validate_frame(frame)};payload["mode"]="shadow"
    store[STORE_KEY]=deepcopy(payload)
    result[STORE_KEY]=deepcopy(payload)
    result.setdefault("functional_events",[])
    for issue in payload["validation"]["issues"]:
        result["functional_events"].append({"type":"canonical_frame_invariant","severity":"high","reason":issue})
    return payload
