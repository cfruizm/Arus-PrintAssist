from app.agent_core_v2_clean.documented_fallback import build_documented_fallback


def item(cid, page, text, source="manual.pdf", title="Manual"):
    return {"id": cid, "page": str(page), "text": text, "title": title, "source": source,
            "metadata": {"canonical_url": source, "page_label": str(page)}}


def test_groups_one_document_and_compresses_pages():
    evidence = [item("R1", 2, "• Ingresar a dispositivos e impresoras"), item("R2", 3, "• Agregar una impresora local"), item("R3", 4, "• Crear un puerto TCP/IP")]
    answer = build_documented_fallback({"generation_evidence": evidence})
    assert answer["text"].count("- Manual") == 1
    assert "páginas 2 a 4" in answer["text"]


def test_discards_legal_page_and_orders_by_physical_page():
    evidence = [item("R5", 7, "• Ingresar el nombre de la impresora"), item("R7", 1, "AVISO LEGAL INFORMACIÓN RESTRINGIDA Y CONFIDENCIAL"), item("R2", 3, "• Agregar una impresora local"), item("R8", 6, "• Seleccionar el controlador")]
    answer = build_documented_fallback({"generation_evidence": evidence})
    text = answer["text"]
    assert "AVISO LEGAL" not in text and "RESTRINGIDA" not in text
    assert text.index("Agregar") < text.index("Seleccionar") < text.index("Ingresar el nombre")
    assert "página 1" not in text
    assert answer["fallback_diagnostics"]["discarded_evidence_count"] == 1


def test_groups_multiple_documents_independently():
    evidence = [item("R1", 2, "• Seleccionar opción A", "a.pdf", "Documento A"), item("R2", 5, "• Finalizar opción A", "a.pdf", "Documento A"), item("R3", 1, "• Confirmar opción B", "b.pdf", "Documento B")]
    answer = build_documented_fallback({"generation_evidence": evidence})
    assert answer["text"].count("- Documento A") == 1
    assert answer["text"].count("- Documento B") == 1
    assert "páginas 2 y 5" in answer["text"]


def test_specific_truncation_reason():
    answer = build_documented_fallback({"generation_evidence": [item("R1", 2, "• Finalizar instalación")]}, "length")
    assert answer["degraded_reason"] == "provider_output_truncated"
