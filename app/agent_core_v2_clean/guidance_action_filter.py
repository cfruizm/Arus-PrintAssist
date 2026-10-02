from __future__ import annotations
import re

_NON_ACTION=("según la documentación","orientación complementaria","basada en conocimiento","fuentes","limitación documental","the documentation","complementary guidance")
_ACTION_HINTS=("verific","revis","comprob","valid","reinici","elimin","configur","desactiv","activ","ejecut","realiz","consult","escal","inspect","check","restart","remove","configure","disable","enable","run","test")

def sanitize_answer_context(context):
    out=dict(context or {});rows=[]
    original=out.get("delivered_guidance") or []
    for item in original:
        action=" ".join(str((item or {}).get("action") or "").split()).strip();low=action.casefold()
        if not action or any(x in low for x in _NON_ACTION):continue
        signature=set((item or {}).get("semantic_signature") or [])
        imperative=any(h in low for h in _ACTION_HINTS) or bool(re.match(r"^(?:debe|debes|puede|puedes|confirme|verifique|revise|realice|ejecute|compruebe)\b",low))
        if not imperative and len(signature)<2:continue
        rows.append(item)
    out["delivered_guidance"]=rows
    out["guidance_filter"]={"policy":"action_only_v1","retained":len(rows),"removed":max(0,len(original)-len(rows))}
    return out
