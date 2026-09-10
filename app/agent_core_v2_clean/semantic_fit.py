from __future__ import annotations
import copy, re, unicodedata
from collections import Counter

VERSION = "semantic_evidence_fit_v1"
STOP = {
    "para","como","que","del","las","los","una","uno","con","por","sin","antes","debo","debe","deben",
    "how","what","the","and","for","from","with","this","that","before","after","into","using",
    "configurar","explicar","realizar","aplicar","validar","revisar","necesito","quiero",
}

def _norm(value):
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.findall(r"[a-z0-9_-]{2,}", value))

def _terms(value):
    return {x for x in _norm(value).split() if x not in STOP and len(x) >= 3}

def _identity(item):
    return str(item.get("url") or item.get("source") or (item.get("metadata") or {}).get("canonical_url") or item.get("title") or "")

def _document_terms(item):
    meta = item.get("metadata") or {}
    return _terms(" ".join(str(x or "") for x in (
        item.get("title"), item.get("text"), meta.get("product"), meta.get("component"),
        meta.get("document_family"), meta.get("source_group"),
    )))

def _rare_title_penalty(title_terms, query_terms):
    if not title_terms:
        return 0.0
    unanchored = title_terms - query_terms
    return min(0.30, 0.06 * len(unanchored))

def evaluate_item(item, query_text, fields=None, answer_context=None):
    fields = fields or {}
    answer_context = answer_context or {}
    stable = " ".join(str(x or "") for x in (
        query_text,
        fields.get("goal"), fields.get("contextual_operation"), fields.get("current_message"),
        " ".join(str(v) for v in (fields.get("details") or {}).values()),
    ))
    q = _terms(stable)
    d = _document_terms(item)
    title_terms = _terms(item.get("title"))
    overlap = q & d
    title_overlap = q & title_terms
    coverage = len(overlap) / max(1, len(q))
    title_coverage = len(title_overlap) / max(1, len(q))
    previous_ids = set(answer_context.get("source_identities") or [])
    continuity_boost = 0.16 if _identity(item) in previous_ids and fields.get("user_act") in {"follow_up", "answer_to_question", "attempt_result", "reported_failure"} else 0.0
    penalty = _rare_title_penalty(title_terms, q)
    score = max(0.0, min(1.0, (0.68 * coverage) + (0.32 * title_coverage) + continuity_boost - penalty))
    return {
        "score": round(score, 4),
        "query_terms": sorted(q),
        "matched_terms": sorted(overlap),
        "title_matched_terms": sorted(title_overlap),
        "unconfirmed_title_terms": sorted(title_terms - q)[:12],
        "continuity_boost": continuity_boost,
        "assumption_penalty": round(penalty, 4),
    }

def apply_semantic_fit(retrieval, answer_context=None):
    result = copy.deepcopy(retrieval or {})
    query = result.get("query") or {}
    query_text = query.get("text") or ""
    fields = query.get("fields") or {}
    ranked = []
    for pos, item in enumerate(result.get("evidence") or []):
        fit = evaluate_item(item, query_text, fields, answer_context)
        row = copy.deepcopy(item)
        row["semantic_fit"] = fit
        ranked.append((fit["score"], -pos, row))
    ranked.sort(reverse=True, key=lambda x: (x[0], x[1]))
    evidence = [x[2] for x in ranked]
    result["evidence"] = evidence
    best = max((x[0] for x in ranked), default=0.0)
    mean_top = sum(x[0] for x in ranked[:3]) / max(1, min(3, len(ranked))) if ranked else 0.0
    prior_quality = float(((result.get("selection") or {}).get("quality") or 0.0))
    combined = round(max(0.0, min(1.0, (0.58 * best) + (0.27 * mean_top) + (0.15 * prior_quality))), 4)
    result.setdefault("selection", {})["quality"] = combined
    result["semantic_fit"] = {
        "version": VERSION,
        "best_score": round(best, 4),
        "mean_top3": round(mean_top, 4),
        "previous_answer_sources_used": bool(answer_context and (answer_context.get("source_identities") or [])),
        "accepted_for_generation": combined >= 0.36,
        "low_fit": combined < 0.36,
        "ranked_ids": [str(x.get("id")) for x in evidence],
    }
    return result

def capture_answer_context(result):
    answer = result.get("answer") or {}
    retrieval = result.get("retrieval") or {}
    if not str(answer.get("text") or "").strip():
        return {}
    cited = set(re.findall(r"\[(R\d+)\]", str(answer.get("text") or "")))
    evidence = retrieval.get("evidence") or []
    chosen = [e for e in evidence if not cited or str(e.get("id")) in cited]
    identities = []
    titles = []
    for item in chosen[:6]:
        identity = _identity(item)
        if identity and identity not in identities:
            identities.append(identity)
        title = str(item.get("title") or "").strip()
        if title and title not in titles:
            titles.append(title)
    text = " ".join(str(answer.get("text") or "").split())
    return {
        "answer_mode": answer.get("mode"),
        "goal": (result.get("understanding") or {}).get("current_goal"),
        "main_text_excerpt": text[:900],
        "source_identities": identities,
        "source_titles": titles,
        "cited_ids": sorted(cited),
        "finish_reason": answer.get("finish_reason"),
        "partial": str(answer.get("mode") or "").endswith("_partial"),
    }
