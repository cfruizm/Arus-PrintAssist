from __future__ import annotations
import json
from .unified_evidence_authority import apply_unified_evidence_verdict
from .documented_answer import repair_qualified_absence_citation
from .guidance_action_filter import sanitize_answer_context

def item(title,score,hits,text="content"):
 return {"id":"X","title":title,"source":"doc://"+title,"text":text,"semantic_fit":{"score":score,"title_matched_terms":hits},"metadata":{}}

def run():
 exact=item("Exact symptom",.51,["jobs","stuck","printing","status"],"jobs stuck printing status troubleshooting")
 broad=item("Broad feature",.38,["printing"],"PaperCut MF provides printing capabilities")
 retrieval={"diagnostic_evidence":[broad,exact],"query":{"fields":{}}}
 understanding={"intent":"conceptual","canonical_subject":"PaperCut MF","current_goal":"identify jobs stuck printing status","goal_updates":{"subject":"PaperCut MF"}}
 out=apply_unified_evidence_verdict(retrieval,"PaperCut MF jobs stuck printing status documentation",understanding)
 text,valid,cited,qualified,repaired=repair_qualified_absence_citation("La documentación no contiene pasos adicionales.",[dict(exact,id="R1")],["R1"])
 context=sanitize_answer_context({"delivered_guidance":[{"action":"Orientación complementaria basada en conocimiento general","semantic_signature":["orientacion","complementaria"]},{"action":"Verifique la cola de impresión","semantic_signature":["verifique","cola","impresion"]}]})
 checks={
  "exact_symptom_wins":out["evidence_verdict"]["reason"]=="exact_symptom_title_precedence" and out["evidence_verdict"]["document_ids"]==["doc://Exact symptom"],
  "qualified_absence_detected":qualified,
  "canonical_citation_inserted":repaired and valid and cited==["R1"] and text.endswith("[R1]"),
  "non_action_removed":context["guidance_filter"]["removed"]==1,
  "action_retained":len(context["delivered_guidance"])==1 and context["delivered_guidance"][0]["action"].startswith("Verifique"),
 }
 failed=[k for k,v in checks.items() if not v]
 return {"phase":"4B.3.6","status":"passed" if not failed else "failed","passed":len(checks)-len(failed),"failed":len(failed),"failed_checks":failed,"checks":checks}
if __name__=="__main__":
 r=run();print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r["status"]=="passed" else 1)
