import ast
from pathlib import Path

def test_current_only_is_defined_before_use():
 tree=ast.parse(Path('app/agent_core_v2_clean/lab_session.py').read_text())
 fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_attach_retrieval')
 source=ast.unparse(fn)
 assert 'current_only = builder.current_only' in source
 assert source.index('current_only = builder.current_only') < source.index('search(built, current_only)')

def test_retrieval_attachment_is_fail_soft():
 text=Path('app/agent_core_v2_clean/lab_session.py').read_text()
 assert 'stage":"retrieval_attachment"' in text
 assert 'except Exception as exc' in text
