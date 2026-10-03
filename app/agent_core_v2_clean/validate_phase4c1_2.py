from __future__ import annotations
import ast,json
from pathlib import Path

def imports(path):
 tree=ast.parse(path.read_text(encoding='utf-8'));out=[]
 for node in ast.walk(tree):
  if isinstance(node,ast.Import):out.extend(x.name for x in node.names)
  elif isinstance(node,ast.ImportFrom):out.append(node.module or '')
 return out

def run():
 root=Path(__file__).resolve().parents[2]
 backend=(root/'app/backend.py').read_text(encoding='utf-8')
 resolver=(root/'app/agent_core_v2_clean/document_resolver.py').read_text(encoding='utf-8')
 expansion=(root/'app/integration/document_expansion_adapter.py').read_text(encoding='utf-8')
 adapter=(root/'app/integration/lab_retrieval_adapter.py').read_text(encoding='utf-8')
 runtime=(root/'app/vectorstore_runtime.py').read_text(encoding='utf-8')
 checks={
  'canonical_runtime_exists':(root/'app/vectorstore_runtime.py').is_file(),
  'backend_reexports_resource':'from app.vectorstore_runtime import' in backend and 'def get_vectorstore()' not in backend,
  'clean_resolver_bypasses_backend':'from app.vectorstore_runtime import get_vectorstore' in resolver and 'from app.backend import get_vectorstore' not in resolver,
  'expansion_bypasses_backend':'from app.vectorstore_runtime import get_vectorstore' in expansion,
  'lab_adapter_bypasses_backend':'from app.vectorstore_runtime import get_vectorstore' in adapter,
  'resource_cache_preserved':'@st.cache_resource' in runtime and 'get_vectorstore_signature' in runtime,
  'no_legacy_imports_in_resource':not any(x.startswith('app.agent_core') or x.startswith('app.integration') for x in imports(root/'app/vectorstore_runtime.py')),
 }
 failed=[k for k,v in checks.items() if not v]
 return {'phase':'4C.1.2','status':'passed' if not failed else 'failed','passed':len(checks)-len(failed),'failed':len(failed),'failed_checks':failed,'checks':checks}
if __name__=='__main__':
 r=run();print(json.dumps(r,indent=2));raise SystemExit(0 if r['status']=='passed' else 1)
