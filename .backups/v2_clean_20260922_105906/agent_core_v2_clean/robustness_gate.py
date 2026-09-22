from __future__ import annotations
GATE_VERSION="minimal-v1"
def build_regression_contracts():return []
def run_gate(assessor):
    fixtures=[{"id":"empty","description":"sin evidencia","input":{"ok":False,"evidence":[],"procedural_expansion":{}},"expected":"insufficient"}]
    results=[]
    for x in fixtures:
        a=assessor(x["input"]);results.append({"case_id":x["id"],"description":x["description"],"passed":a.status==x["expected"],"expected":x["expected"],"observed":a.status,"mismatches":[] if a.status==x["expected"] else [a.status]})
    return {"gate":"agent_core_v2_clean_minimal","approved":all(x["passed"] for x in results),"passed":sum(x["passed"] for x in results),"failed":sum(not x["passed"] for x in results),"llm_calls":0,"tokens":0,"results":results}
def write_report(path,assessor):
    import json
    r=run_gate(assessor);open(path,"w",encoding="utf-8").write(json.dumps(r,ensure_ascii=False,indent=2));return r
