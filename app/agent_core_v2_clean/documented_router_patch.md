# Ajuste requerido en documented_router.py

En el diagnóstico de `internal_knowledge`, agregar:

```python
"attempts": deepcopy(composer.attempts),
"retry_used": bool(composer.validation.get("retry_used")),
"selected_evidence_ids": deepcopy(composer.validation.get("selected_evidence_ids", [])),
```

Para telemetría correcta cuando haya reintento, registrar cada elemento de `composer.attempts` en lugar de contabilizar únicamente `composer.last_provider_result`. Si `lab_session.py` ya registra una sola traza devuelta por el router, mantener la traza agregada, pero sumar en `turn_metrics.calls` la longitud de `attempts`.
