from __future__ import annotations
import argparse, csv, importlib, json, os
from pathlib import Path


def load_callable(spec: str):
    module_name, function_name = spec.split(":", 1)
    return getattr(importlib.import_module(module_name), function_name)


def main():
    parser = argparse.ArgumentParser(description="Run read-only retrieval shadow comparison. No LLM calls.")
    parser.add_argument("--legacy", required=True, help="module:function accepting query")
    parser.add_argument("--candidate", required=True, help="module:function accepting query, product ids, process ids, exact url")
    parser.add_argument("--queries", default="approved_shadow_queries.json")
    parser.add_argument("--output", default="shadow_report.json")
    args = parser.parse_args()

    os.environ["AGENT_CORE_V1_SHADOW_ENABLED"] = "true"
    from app.retrieval.shadow_compare import compare_retrieval

    legacy = load_callable(args.legacy); candidate = load_callable(args.candidate)
    cases = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    records = []
    for case in cases:
        result = compare_retrieval(case["query"], legacy, candidate)
        records.append({"id": case["id"], "category": case["category"], **result.__dict__})
        print(case["id"], "top1=", result.top1_match, "top3=", round(result.top3_overlap, 3), "errors=", result.legacy_error, result.candidate_error)
    summary = {
        "total": len(records),
        "top1_match_rate": sum(r["top1_match"] for r in records) / max(1, len(records)),
        "mean_top3_overlap": sum(r["top3_overlap"] for r in records) / max(1, len(records)),
        "llm_calls": 0,
        "records": records,
    }
    Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Report:", args.output)

if __name__ == "__main__": main()
