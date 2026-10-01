from app.agent_core_v2_clean.documented_enumeration import ensure_enumeration_completeness

EVIDENCE = [{
    "id": "R8",
    "text": (
        "443 I R TCP La comunicacion de servicios web HTTP mediante SSL/TLS se dirige a este puerto. "
        "5222 I R TCP Mensajeria XMPP segura mediante TLS para transmitir datos de control. "
        "3702 i R UDP Descubrimiento de servicios web en dispositivos."
    ),
}]


def run():
    checks = []
    def check(name, condition):
        checks.append((name, bool(condition)))

    repaired, diag = ensure_enumeration_completeness(
        "Y cual de esos puertos utiliza TLS?",
        "El puerto documentado es 443. [R8]",
        EVIDENCE,
    )
    check("detects_property", diag.get("property_term") == "tls")
    check("finds_documented_values", diag.get("documented_values") == ["443", "5222"])
    check("repairs_missing_value", "5222" in repaired and diag.get("repaired") is True)
    check("does_not_add_unrelated_value", "3702" not in repaired)
    check("keeps_canonical_citation", repaired.count("[R8]") >= 2)

    complete, complete_diag = ensure_enumeration_completeness(
        "Y cual de esos puertos utiliza TLS?",
        "Los puertos son 443 y 5222. [R8]",
        EVIDENCE,
    )
    check("complete_answer_unchanged", complete == "Los puertos son 443 y 5222. [R8]")
    check("complete_answer_not_repaired", complete_diag.get("repaired") is False)

    broad, broad_diag = ensure_enumeration_completeness(
        "Que requisitos debo tener para instalar el sistema?",
        "Se requieren sistema operativo y conectividad. [R8]",
        EVIDENCE,
    )
    check("broad_query_unchanged", broad == "Se requieren sistema operativo y conectividad. [R8]")
    check("broad_query_not_repaired", broad_diag.get("repaired") is False)

    failed = [name for name, ok in checks if not ok]
    print({"passed": len(checks)-len(failed), "failed": len(failed), "failures": failed})
    if failed:
        raise SystemExit(1)

if __name__ == "__main__":
    run()
