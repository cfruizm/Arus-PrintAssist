from __future__ import annotations
import json
from .applicability_language import normalize_conditional_applicability
from .runtime_memory import compact_cache_artifact,enforce_runtime_memory_limits,memory_diagnostic

REAL_SHAPE='''Dado que las validaciones anteriores no resolvieron el problema, la documentación indica que la causa probable es una combinación de condiciones no confirmadas [R4].

El siguiente paso documentado es aplicar una de las dos soluciones:

1. **Alternativa A:** Implementa el cambio indicado por la documentación [R3].
2. **Alternativa B:** Si el entorno utiliza la configuración descrita, aplica la segunda opción [R1].

Verifica primero si las condiciones documentadas aplican al entorno antes de realizar cambios [R4].

**Fuente documental:** [Documento autorizado](https://example.invalid/doc)'''


def run():
    repaired,changed,diag=normalize_conditional_applicability(REAL_SHAPE)
    ordinary='''La documentación recomienda revisar la cola [R1].

Después valida el servicio [R2].

**Fuente documental:** [Documento](https://example.invalid/doc)'''
    ordinary_out,ordinary_changed,_=normalize_conditional_applicability(ordinary)
    conditional_without_verify='''El siguiente paso es aplicar el cambio.

Si el entorno utiliza esa configuración, aplica la alternativa [R1].'''
    cautious,cautious_changed,cautious_diag=normalize_conditional_applicability(conditional_without_verify)
    artifact=compact_cache_artifact({"answer":{"text":"ok"},"retrieval":{"diagnostic_evidence":[{"text":"x"*5000}],"evidence_verdict":{"status":"sufficient"}},"answer_context":{"active_document_evidence_ledger":[{"text":"y"*5000}]}})
    store={"turns":[],"messages":[],"errors":[],"answer_context":{},"cache_metrics":{"configured_limits":{"exact_turn_cache":8}},"exact_turn_cache":{"a":{"artifact":artifact},"b":{"artifact":artifact}},"retrieval_cache":{},"documented_answer_cache":{},"procedural_answer_cache":{},"internal_knowledge_cache":{}}
    enforce_runtime_memory_limits(store);mem=memory_diagnostic(store)
    checks={
      "causal_overclaim_removed":"causa probable" not in repaired,
      "direct_step_intro_removed":"siguiente paso documentado" not in repaired,
      "verification_is_first":repaired.startswith("Verifica primero"),
      "conditional_bridge_precedes_actions":repaired.index("Si la verificación confirma") < repaired.index("1. **Alternativa A:**"),
      "cited_procedures_preserved":all(x in repaired for x in ("[R1]","[R3]","[R4]","**Fuente documental:**")),
      "normal_answer_unchanged":not ordinary_changed and ordinary_out==ordinary,
      "no_repair_without_explicit_verify_authority":not cautious_changed and cautious==conditional_without_verify and cautious_diag["reason"]=="no_explicit_verify_first_authority",
      "diagnostic_complete":diag["removed_causal_claims"]==1 and diag["removed_direct_introductions"]==1,
      "memory_guard_preserved":mem["policy"]=="bounded_session_v2" and mem["cache_summary"]["exact_turn_cache"]["entries"]==1,
    }
    failed=[k for k,v in checks.items() if not v]
    return {"phase":"4B.3.10","status":"passed" if not failed else "failed","passed":len(checks)-len(failed),"failed":len(failed),"failed_checks":failed,"checks":checks}
if __name__=="__main__":
    r=run();print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r["status"]=="passed" else 1)
