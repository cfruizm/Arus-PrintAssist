import re, unicodedata

def norm(v):
    t=unicodedata.normalize("NFKD",str(v or "").lower()); t="".join(c for c in t if not unicodedata.combining(c)); return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9\s]"," ",t)).strip()
def contains(text,alias):
    a=norm(alias); return bool(a and re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])",text))
def detect(message, registry):
    text=norm(message); found=[]
    for eid,item in registry.items():
        aliases=[item.get("canonical_name","")]+list(item.get("aliases") or [])
        if any(contains(text,a) for a in aliases): found.append(eid)
    return found
