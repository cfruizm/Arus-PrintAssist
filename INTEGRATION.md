# Integración obligatoria

## 1. Botón existente “Nueva conversación”
En la función que atiende el botón de la página existente, sustituir el borrado parcial por:

```python
from app.agent_core_v2_clean.session_lifecycle import reset_new_conversation

reset_new_conversation(
    st.session_state,
    cache_clearers=[
        lab.clear_exact_turn_cache,
        lab.clear_retrieval_cache,
        lab.clear_answer_caches,
    ],
)
st.rerun()
```

Adapta únicamente los nombres de los tres métodos `clear_*` a los métodos reales ya existentes. Si las cachés pertenecen al objeto de laboratorio, deben limpiarse antes de descartar ese objeto.

El evento debe crear de nuevo el gateway o el presupuesto de sesión usando la nueva telemetría. No debe reutilizar el objeto anterior.

No usar `st.cache_resource.clear()` globalmente porque eliminaría vectorstore y objetos compartidos de producción.

## 2. Diagnóstico visible y exportado
Antes de ejecutar cada turno, agregar al JSON:

```python
budget_snapshot(runtime, budget.max_session_tokens, budget.reserve_tokens)
```

Así podremos diferenciar límite real de sesión y límite del proveedor.

## 3. Recuperación después de guardia procedural
En `documented_router.py`, inmediatamente después de generar y validar una respuesta procedural:

```python
from .recovery_policy import should_recover_with_controlled_knowledge, recovery_diagnostic

if should_recover_with_controlled_knowledge(answer, assessment):
    diagnostics["procedural_recovery"] = recovery_diagnostic(answer.mode)
    answer = compose_controlled_internal_knowledge(...)
```

La recuperación se ejecuta una sola vez. No se cachea la guardia. Solo la respuesta final validada puede cerrar el objetivo y entrar en caché.

## 4. Estado transaccional
Si el gateway rechaza un turno antes de producir respuesta final, no avanzar `turn_number`, no cerrar el objetivo y no reemplazar el tema activo. Registrar el intento fallido aparte.

## 5. Aplicabilidad del conocimiento interno
En `internal_knowledge.py`, al construir el mensaje de sistema:

```python
from .internal_knowledge_policy import apply_context_policy
system_prompt = apply_context_policy(SYSTEM)
```

Usar `system_prompt` en la llamada al gateway. Esto evita introducir mecanismos de identidad en firmware u operaciones no relacionadas.
