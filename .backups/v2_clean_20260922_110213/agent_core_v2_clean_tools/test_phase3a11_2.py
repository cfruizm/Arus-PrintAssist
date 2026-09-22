from app.agent_core_v2_clean.citation_finalizer import finalize_citations, enforce_answer_contract


def plan(allow, ids=None, mapping=None):
    return {
        "evidence_plan": {"documented_ids": ids or [], "citation_map": mapping or {}},
        "response_plan": {"allow_documented_claims": allow},
    }


def test_original_id_is_remapped_to_final_registry_id():
    text, audit = finalize_citations("Paso soportado [R8].", plan(True, ["R1"], {"R8": "R1"}))
    assert text == "Paso soportado [R1]."
    assert audit.valid and audit.remapped_ids == {"R8": "R1"}


def test_unknown_id_is_detected_without_silent_acceptance():
    _, audit = finalize_citations("Paso [R9].", plan(True, ["R1"]))
    assert not audit.valid and audit.unknown_ids == ["R9"]


def test_internal_mode_strips_all_documentary_citations():
    text, audit = finalize_citations("Consejo general [R4].\n\n**Fuentes documentales**\n- [R4] Documento", plan(False))
    assert "[R4]" not in text and "Fuentes documentales" not in text
    assert audit.valid and audit.stripped_ids == ["R4"]


def test_answer_flags_follow_final_citation_audit():
    payload = {"text": "Orientación [R4].", "internal_knowledge_used": True, "documented_evidence_used": True}
    out, audit = enforce_answer_contract(payload, plan(False))
    assert out["knowledge_mode"] == "internal_only"
    assert out["documented_evidence_used"] is False
    assert audit["valid"] is True


def test_documented_answer_keeps_valid_registered_citation():
    payload = {"text": "Paso [R1].", "internal_knowledge_used": False}
    out, audit = enforce_answer_contract(payload, plan(True, ["R1"]))
    assert out["documented_evidence_used"] is True
    assert out["knowledge_mode"] == "documented_only"
    assert audit["unknown_ids"] == []
