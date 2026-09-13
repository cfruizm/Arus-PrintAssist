from __future__ import annotations

def compact_documented_instruction() -> str:
    return (
        "Reescribe la respuesta usando exclusivamente la evidencia documental autorizada. "
        "Conserva todas las operaciones principales, pero resume cada alternativa en uno o dos pasos. "
        "No agregues conocimiento general, no repitas requisitos y no incluyas una sección complementaria. "
        "Mantén las citas junto a cada afirmación y termina la respuesta completa dentro del límite."
    )

def should_compact_retry(provider_result) -> bool:
    if isinstance(provider_result, dict):
        finish = provider_result.get("finish_reason")
    else:
        finish = getattr(provider_result, "finish_reason", None)
    return finish in {"length", "max_tokens"}
