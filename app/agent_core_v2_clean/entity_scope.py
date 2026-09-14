from __future__ import annotations
from dataclasses import dataclass, asdict

ALIASES = {
    "manufacturer": {"manufacturer", "brand", "vendor", "fabricante", "marca"},
    "product": {"product", "platform", "solution", "producto", "plataforma", "solucion"},
    "model": {"model", "device_model", "printer_model", "modelo"},
    "operating_system": {"operating_system", "os", "sistema_operativo"},
    "architecture": {"architecture", "arch", "arquitectura"},
}

@dataclass(frozen=True)
class CanonicalScope:
    manufacturer: str | None = None
    product: str | None = None
    model: str | None = None
    operating_system: str | None = None
    architecture: str | None = None
    def to_dict(self): return asdict(self)
    def explicit_fields(self): return [k for k,v in self.to_dict().items() if v]

def normalize_scope(details: dict | None) -> CanonicalScope:
    raw = {str(k).casefold(): str(v).strip() for k,v in (details or {}).items() if str(v).strip()}
    values = {}
    for canonical, aliases in ALIASES.items():
        values[canonical] = next((raw[a] for a in aliases if a in raw), None)
    return CanonicalScope(**values)

def merge_scope(*details: dict | None) -> CanonicalScope:
    merged = {}
    for block in details:
        scope = normalize_scope(block).to_dict()
        for key,value in scope.items():
            if value: merged[key] = value
    return CanonicalScope(**merged)
