from __future__ import annotations
import re
import unicodedata

# Generic evidence-coverage guard. It does not know products, protocols, ports,
# documents, or campaign phrases. It only compares numeric facts attached to a
# property explicitly present in the user's question with values published in
# the drafted answer.
_GENERIC_WORDS = {
    "cual", "cuales", "que", "como", "donde", "cuando", "esos", "esas",
    "este", "esta", "estos", "estas", "documenta", "documentado", "fuente",
    "utiliza", "utilizan", "usa", "usan", "tiene", "tienen", "para", "con",
    "del", "las", "los", "una", "uno", "unos", "unas", "and", "the", "which",
    "what", "that", "those", "uses", "use", "documented", "source",
}

def _norm(value):
    text=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode("ascii").casefold()
    return re.sub(r"\s+"," ",text).strip()

def _property_terms(question):
    raw=re.findall(r"[a-z0-9][a-z0-9_.+/-]*",_norm(question))
    return {x for x in raw if x not in _GENERIC_WORDS and (len(x)>=3 or any(ch.isdigit() for ch in x))}

def _numeric_values(text):
    return set(re.findall(r"(?<![A-Za-z0-9])\d{2,6}(?![A-Za-z0-9])",str(text or "")))

def ensure_enumerated_numeric_fact_coverage(text, question, evidence, minimum=2, maximum=8, repair_limit=4):
    """Append explicitly documented omitted numeric facts for a requested property.

    Activation is intentionally narrow: at least two and at most eight distinct
    numeric values must occur in evidence sentences that also include a
    discriminative property term from the user's question. This prevents the
    guard from changing broad requirements answers or unrelated prose.
    """
    terms=_property_terms(question)
    diagnostic={"checked":False,"property_terms":sorted(terms),"documented_values":[],"response_values":sorted(_numeric_values(text)),"missing_values":[],"repaired":False}
    if not terms:
        return text,diagnostic
    candidates={}
    for row in list(evidence or []):
        rid=str(row.get("id") or "").strip()
        body=str(row.get("text") or row.get("content") or "")
        for sentence in re.split(r"(?<=[.!?;])\s+|[\r\n]+",body):
            normalized=_norm(sentence)
            if not normalized or not any(term in normalized for term in terms):
                continue
            for value in _numeric_values(sentence):
                candidates.setdefault(value,{"id":rid,"sentence":sentence.strip()})
    values=sorted(candidates,key=lambda x:int(x))
    diagnostic["documented_values"]=values
    if not (minimum <= len(values) <= maximum):
        return text,diagnostic
    diagnostic["checked"]=True
    present=_numeric_values(text)
    missing=[value for value in values if value not in present]
    diagnostic["missing_values"]=missing
    if not missing or len(missing)>repair_limit:
        return text,diagnostic
    lines=[]
    used=set()
    for value in missing:
        item=candidates[value]
        key=(item["id"],item["sentence"])
        if key in used: continue
        used.add(key)
        citation=f" [{item['id']}]" if item["id"] else ""
        sentence=item["sentence"].rstrip(" .")
        lines.append(f"- {sentence}.{citation}")
    if not lines:
        return text,diagnostic
    diagnostic["repaired"]=True
    diagnostic["added_values"]=missing
    return str(text or "").rstrip()+"\n\n**Cobertura documental adicional**\n\n"+"\n".join(lines),diagnostic
