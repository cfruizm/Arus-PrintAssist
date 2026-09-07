from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Make project imports independent from the shell working directory.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("El archivo de escenarios debe contener una lista no vacia.")
    return [item for item in data if isinstance(item, dict)]


def select_scenario(rows: list[dict[str, Any]], scenario_id: str) -> dict[str, Any]:
    matches = [row for row in rows if str(row.get("id") or "") == scenario_id]
    if len(matches) != 1:
        available = ", ".join(str(row.get("id")) for row in rows)
        raise ValueError(f"Escenario '{scenario_id}' no encontrado. Disponibles: {available}")
    return matches[0]


def build_secrets() -> dict[str, Any]:
    keys = (
        "LLM_PROVIDER", "LLM_FALLBACK_ENABLED", "LLM_FALLBACK_PROVIDER",
        "LLM_MAX_CALLS_PER_SESSION", "LLM_MAX_TOTAL_TOKENS_PER_SESSION",
        "GROQ_API_KEY", "GROQ_ORCHESTRATOR_MODEL", "GROQ_ANSWER_MODEL",
        "GROQ_STRUCTURED_OUTPUT_MODE", "HF_TOKEN", "HF_MODEL",
        "HF_ORCHESTRATOR_MODEL", "HF_ANSWER_MODEL", "HF_PROVIDER",
        "LLM_ORCHESTRATOR_MAX_TOKENS", "LLM_EVIDENCE_JUDGE_MAX_TOKENS",
        "LLM_ANSWER_MAX_TOKENS", "AGENT_CORE_V2_INITIAL_CANDIDATES",
        "AGENT_CORE_V2_MAX_CANDIDATES",
    )
    values = {key: os.environ[key] for key in keys if os.environ.get(key) not in (None, "")}
    values.setdefault("LLM_PROVIDER", "groq")
    values.setdefault("LLM_FALLBACK_ENABLED", False)
    values.setdefault("LLM_MAX_CALLS_PER_SESSION", "6")
    values.setdefault("LLM_MAX_TOTAL_TOKENS_PER_SESSION", "4000")
    values.setdefault("LLM_ORCHESTRATOR_MAX_TOKENS", "220")
    values.setdefault("LLM_EVIDENCE_JUDGE_MAX_TOKENS", "260")
    values.setdefault("LLM_ANSWER_MAX_TOKENS", "380")
    values.setdefault("AGENT_CORE_V2_INITIAL_CANDIDATES", "3")
    values.setdefault("AGENT_CORE_V2_MAX_CANDIDATES", "5")
    return values


def preflight(secrets: dict[str, Any]) -> dict[str, Any]:
    provider = str(secrets.get("LLM_PROVIDER") or "groq").strip().lower()
    required = "GROQ_API_KEY" if provider == "groq" else "HF_TOKEN"
    if not secrets.get(required):
        raise RuntimeError(f"Falta el secreto requerido para {provider}: {required}")
    import app
    from app.agent_core_v2.real_lab import run_real_scenario
    return {
        "provider": provider,
        "required_secret_present": True,
        "repository_root": str(REPOSITORY_ROOT),
        "app_import": "passed",
        "real_lab_import": "passed",
    }


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    usage = result.get("usage") or {}
    return {
        "scenario_id": result.get("scenario_id"),
        "name": result.get("name"),
        "status": result.get("status"),
        "functional_result": result.get("functional_result"),
        "checkpoint_passed": bool(result.get("checkpoint_passed")),
        "error": result.get("error"),
        "usage": {
            "calls": int(usage.get("calls", 0) or 0),
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
        },
        "adaptive_savings": result.get("adaptive_savings") or {},
        "latency_evaluated": False,
        "production_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta un escenario real controlado de Agent Core v2.")
    parser.add_argument("--scenario", default="monitoring")
    parser.add_argument("--scenarios-file", default=str(REPOSITORY_ROOT / "tools/agent_core_v2/real_lab_scenarios.json"))
    parser.add_argument("--output", default=str(REPOSITORY_ROOT / "artifacts/agent_core_v2_real_lab.json"))
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    envelope: dict[str, Any] = {
        "lab": "agent_core_v2_controlled_real_lab",
        "requested_scenario": args.scenario,
        "preflight": "pending",
        "production_changed": False,
        "latency_evaluated": False,
    }
    try:
        rows = load_scenarios(Path(args.scenarios_file))
        scenario = select_scenario(rows, args.scenario)
        secrets = build_secrets()
        envelope["preflight_checks"] = preflight(secrets)
        envelope["preflight"] = "passed"
        from app.agent_core_v2.real_lab import run_real_scenario
        result = run_real_scenario(scenario, secrets, {})
        envelope["result"] = result
        envelope["summary"] = compact_result(result)
        passed = result.get("status") == "ok" and bool(result.get("checkpoint_passed"))
        envelope["status"] = "passed" if passed else "failed"
    except Exception as exc:
        envelope["preflight"] = "failed" if envelope["preflight"] == "pending" else envelope["preflight"]
        envelope["status"] = "error"
        envelope["error"] = f"{type(exc).__name__}: {exc}"
    output.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(envelope.get("summary", envelope), ensure_ascii=False, indent=2))
    print(f"Reporte completo: {output}")
    return 0 if envelope.get("status") == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
