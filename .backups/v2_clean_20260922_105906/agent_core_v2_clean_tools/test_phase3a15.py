from app.agent_core_v2_clean.citation_finalizer import finalize_citations
from app.agent_core_v2_clean.semantic_fit import apply_semantic_fit


def _plan():
    evidence = [
        {"id": "R1", "title": "Procedimiento técnico", "source": "/doc.pdf", "page": "2", "text": "inicio"},
        {"id": "R3", "title": "Procedimiento técnico", "source": "/doc.pdf", "page": "4", "text": "configuración"},
        {"id": "R4", "title": "Procedimiento técnico", "source": "/doc.pdf", "page": "5", "text": "selección"},
        {"id": "R5", "title": "Procedimiento técnico", "source": "/doc.pdf", "page": "6", "text": "ruta"},
        {"id": "R6", "title": "Procedimiento técnico", "source": "/doc.pdf", "page": "7", "text": "instalación"},
        {"id": "R7", "title": "Procedimiento técnico", "source": "/doc.pdf", "page": "8", "text": "finalización"},
    ]
    return {"evidence_plan": {"documented_ids": [x["id"] for x in evidence], "selected_evidence": evidence, "citation_namespace": "canonical"}, "response_plan": {"allow_documented_claims": True}}


def test_sources_are_grouped_and_pages_are_compacted():
    text = "Paso [R1]. Otro [R3][R4][R5][R6][R7].\n\n**Fuentes documentales**\n- [R1] Procedimiento técnico, página 2\n- [R3] Procedimiento técnico, página 4"
    result, audit = finalize_citations(text, _plan())
    assert audit.valid
    assert result.count("- Procedimiento técnico") == 1
    assert "páginas 2 y 4 a 8" in result
    assert "- [R1]" not in result


def test_primary_followup_evidence_can_clear_general_threshold():
    retrieval = {"query": {"text": "determinar detección automática controlador instalación punto a punto", "fields": {"intent": "requirements", "topic_relation": "same_topic_refinement", "previous_evidence_role": "primary", "user_act": "request_elaboration"}}, "evidence": [], "selection": {"quality": 0.0}}
    context = {"source_identities": ["/driver.pdf"], "cited_evidence": [{"id": "R2", "title": "Instalar driver punto a punto", "source": "/driver.pdf", "page": "4", "text": "Retirar la opción consultar la impresora y seleccionar automáticamente el controlador durante la instalación."}]}
    result = apply_semantic_fit(retrieval, context)
    assert result["semantic_fit"]["accepted_for_generation"] is True
    assert result["semantic_fit"]["carried_previous_evidence"] == 1
    assert result["followup_grounding"]["previous_evidence_selected"] == 1
