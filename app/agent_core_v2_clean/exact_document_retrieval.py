from __future__ import annotations
import re, unicodedata

_CODE = re.compile(r"\b[A-Za-z]{2,}\d{3,}(?:[-_][A-Za-z0-9]+)*\b")

def norm(value):
    text=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode().casefold()
    return ' '.join(re.findall(r'[a-z0-9]+',text))

def document_identifiers(*values):
    out=[]
    for value in values:
        for match in _CODE.findall(str(value or '')):
            key=norm(match)
            if key and key not in out:out.append(key)
    return out

def query_variants(message,goal,subject):
    ids=document_identifiers(message,goal,subject)
    if not ids:return []
    title=' '.join(str(subject or goal or message or '').split())
    variants=[]
    for identifier in ids:
        compact=identifier.replace(' ','')
        dashed='-'.join(identifier.split())
        underscored='_'.join(identifier.split())
        for value in (compact,dashed,underscored,identifier,title):
            value=' '.join(str(value or '').split())
            if value and value.casefold() not in {x.casefold() for x in variants}:variants.append(value)
    return variants[:8]

def exact_matches(items,identifiers):
    matches=[]
    for item in items or []:
        hay=norm(' '.join(str(x or '') for x in (item.get('title'),item.get('source'),item.get('url'),(item.get('metadata') or {}).get('source_name'),(item.get('metadata') or {}).get('title'))))
        if any(identifier in hay for identifier in identifiers):matches.append(item)
    return matches
