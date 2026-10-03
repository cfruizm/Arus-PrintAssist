from __future__ import annotations
import ast,builtins,json
from pathlib import Path

def _loaded_names(path):
 import symtable
 text=path.read_text(encoding="utf-8");table=symtable.symtable(text,str(path),"exec")
 module_defined={x.get_name() for x in table.get_symbols() if x.is_imported() or x.is_assigned() or x.is_namespace()}
 global_refs=set()
 stack=list(table.get_children())
 while stack:
  child=stack.pop();stack.extend(child.get_children())
  global_refs.update(x.get_name() for x in child.get_symbols() if x.is_referenced() and x.is_global())
 return global_refs,module_defined|set(dir(builtins))

def run():
 root=Path(__file__).resolve().parents[2];runtime=root/'app/retrieval_runtime.py';backend=root/'app/backend.py';adapter=root/'app/integration/lab_retrieval_adapter.py'
 runtime_text=runtime.read_text(encoding='utf-8');backend_text=backend.read_text(encoding='utf-8');adapter_text=adapter.read_text(encoding='utf-8');loaded,defined=_loaded_names(runtime)
 unresolved=sorted(x for x in loaded-defined if not x.startswith('_'))
 checks={
  'retrieval_runtime_exists':runtime.is_file(),
  'productive_adapter_uses_runtime':'from app.retrieval_runtime import retrieve_context' in adapter_text and 'from app.backend import retrieve_context' not in adapter_text,
  'adapter_identity_updated':'app.retrieval_runtime.retrieve_context' in adapter_text,
  'backend_is_compatibility_delegate':'from app.retrieval_runtime import retrieve_context as _retrieve_context' in backend_text,
  'runtime_owns_retrieve_context':'def retrieve_context(query: str, top_k: int = 4)' in runtime_text,
  'runtime_uses_vectorstore_boundary':'from app.vectorstore_runtime import get_vectorstore' in runtime_text,
  'runtime_has_no_legacy_imports':all(x not in runtime_text for x in ('app.agent_core','app.agent_core_v2','app.integration','app.backend')),
  'runtime_names_resolved':not unresolved,
 }
 failed=[k for k,v in checks.items() if not v]
 return {'phase':'4C.1.3','status':'passed' if not failed else 'failed','passed':len(checks)-len(failed),'failed':len(failed),'failed_checks':failed,'unresolved_names':unresolved,'checks':checks}
if __name__=='__main__':
 r=run();print(json.dumps(r,indent=2));raise SystemExit(0 if r['status']=='passed' else 1)
