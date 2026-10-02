from __future__ import annotations
import json
from .applicability_language import guard_unconfirmed_applicability
from .runtime_memory import compact_cache_artifact,enforce_runtime_memory_limits,memory_diagnostic

def run():
    original='''Dado que las revisiones previas no resolvieron el problema, el siguiente paso documentado es cambiar la configuración del controlador.

Si el entorno utiliza esa modalidad de autenticación y los trabajos provienen de la aplicación afectada, la documentación recomienda deshabilitar temporalmente esa opción [R1].

Alternativamente, si aplica otra modalidad de renderizado, valida primero esa condición [R2].'''
    repaired,changed,diag=guard_unconfirmed_applicability(original)
    safe='''La documentación recomienda revisar la cola [R1].

Después valida el estado del servicio [R2].'''
    safe_out,safe_changed,_=guard_unconfirmed_applicability(safe)
    artifact=compact_cache_artifact({"answer":{"text":"ok"},"retrieval":{"diagnostic_evidence":[{"text":"x"*5000}],"evidence_verdict":{"status":"sufficient"}},"answer_context":{"active_document_evidence_ledger":[{"text":"y"*5000}]}})
    store={"turns":[],"messages":[],"errors":[],"answer_context":{},"cache_metrics":{"configured_limits":{"exact_turn_cache":8}},"exact_turn_cache":{"a":{"artifact":artifact},"b":{"artifact":artifact}},"retrieval_cache":{},"documented_answer_cache":{},"procedural_answer_cache":{},"internal_knowledge_cache":{}}
    enforce_runtime_memory_limits(store);mem=memory_diagnostic(store)
    checks={
      "universal_lead_removed":changed and "siguiente paso documentado" not in repaired,
      "conditional_cited_guidance_preserved":"Si el entorno" in repaired and "[R1]" in repaired and "[R2]" in repaired,
      "no_new_procedure_invented":"deshabilitar temporalmente" in repaired,
      "normal_answer_unchanged":not safe_changed and safe_out==safe,
      "diagnostic_explains_repair":diag["reason"]=="universal_lead_removed_before_conditional_guidance",
      "memory_v2_preserved":mem["policy"]=="bounded_session_v2" and mem["cache_summary"]["exact_turn_cache"]["entries"]==1,
    }
    failed=[k for k,v in checks.items() if not v]
    return {"phase":"4B.3.9","status":"passed" if not failed else "failed","passed":len(checks)-len(failed),"failed":len(failed),"failed_checks":failed,"checks":checks}
if __name__=="__main__":
    r=run();print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r["status"]=="passed" else 1)
