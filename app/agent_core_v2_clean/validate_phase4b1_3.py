from __future__ import annotations
from .documented_fact_coverage import ensure_enumerated_numeric_fact_coverage
from .phase_version import PHASE,FORMAT

def run():
 evidence=[
  {"id":"R1","text":"443 TCP: secure web communication using TLS."},
  {"id":"R2","text":"5222 TCP: secure messaging using TLS."},
  {"id":"R3","text":"3702 UDP: discovery traffic without the requested property."},
 ]
 repaired,diag=ensure_enumerated_numeric_fact_coverage("El puerto documentado es 443. [R1]","Which documented ports use TLS?",evidence)
 complete,diag2=ensure_enumerated_numeric_fact_coverage("Los puertos son 443 [R1] y 5222 [R2].","Which documented ports use TLS?",evidence)
 broad,diag3=ensure_enumerated_numeric_fact_coverage("Resumen.","What requirements apply?",evidence)
 checks={
  "phase":PHASE=="4B.1.3",
  "format":FORMAT=="henkia_support_assist_4b1_3_documented_enumeration_completeness",
  "omitted_value_added":"5222" in repaired,
  "unsupported_value_not_added":"3702" not in repaired,
  "canonical_citation_added":"[R2]" in repaired,
  "repair_recorded":diag.get("repaired") is True,
  "complete_answer_unchanged":complete=="Los puertos son 443 [R1] y 5222 [R2]." and not diag2.get("repaired"),
  "broad_question_unchanged":broad=="Resumen." and not diag3.get("repaired"),
 }
 return checks

if __name__=='__main__':
 c=run();print(c);raise SystemExit(0 if all(c.values()) else 1)
