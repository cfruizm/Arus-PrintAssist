from __future__ import annotations
import argparse, ast, json, py_compile, sys
from dataclasses import asdict, dataclass
from pathlib import Path

@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    blocking: bool = True

REQUIRED = {
    "models.py": ("ConversationState", "CanonicalDecision"),
    "engine.py": ("TurnEngine",),
    "decision.py": ("DecisionReconciler",),
    "transitions.py": ("TransitionEngine",),
    "contextual_query.py": ("ContextualRetrievalQueryBuilder",),
    "semantic_evidence_pipeline.py": ("SemanticEvidencePipeline",),
    "response.py": ("ResponseComposer",),
    "scope_checkpoint.py": ("scope_checkpoint",),
}
SCENARIOS = ("benchmark_conversations.json", "multiturn_scenarios.json", "real_lab_scenarios.json")

def check(name, passed, detail): return Check(name, bool(passed), detail)
def definitions(path):
    tree=ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {n.name for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))}

def compile_check(root):
    files=sorted((root/"app/agent_core_v2").glob("*.py"))+sorted((root/"tools/agent_core_v2").glob("*.py")); errors=[]
    for path in files:
        try: py_compile.compile(str(path),doraise=True)
        except py_compile.PyCompileError as exc: errors.append(f"{path.relative_to(root)}: {exc.msg}")
    return check("python_compiles",files and not errors,f"{len(files)} archivos compilados" if not errors else "; ".join(errors))

def runtime_check(root):
    base=root/"app/agent_core_v2"; errors=[]
    for filename,symbols in REQUIRED.items():
        path=base/filename
        if not path.exists(): errors.append(f"falta {filename}"); continue
        try: present=definitions(path)
        except SyntaxError as exc: errors.append(f"{filename}: sintaxis invalida linea {exc.lineno}"); continue
        missing=[s for s in symbols if s not in present]
        if missing: errors.append(f"{filename}: faltan {', '.join(missing)}")
    return check("runtime_contracts_present",not errors,"contratos estructurales completos" if not errors else "; ".join(errors))

def scenario_check(root):
    base=root/"tools/agent_core_v2"; errors=[]; total=0; multiturn=[]
    for filename in SCENARIOS:
        path=base/filename
        if not path.exists(): errors.append(f"falta {filename}"); continue
        try: rows=json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc: errors.append(f"{filename}: {exc}"); continue
        if not isinstance(rows,list) or not rows: errors.append(f"{filename}: raiz vacia o invalida"); continue
        seen=set()
        for i,row in enumerate(rows):
            total+=1
            if not isinstance(row,dict): errors.append(f"{filename}[{i}]: no es objeto"); continue
            sid=str(row.get("id") or "").strip(); messages=row.get("messages")
            if messages is None and isinstance(row.get("turns"),list):
                messages=[turn.get("message") for turn in row["turns"] if isinstance(turn,dict)]
            if not sid: errors.append(f"{filename}[{i}]: id vacio")
            if sid in seen: errors.append(f"{filename}: id duplicado {sid}")
            seen.add(sid)
            if not isinstance(messages,list) or not messages or not all(isinstance(m,str) and m.strip() for m in messages): errors.append(f"{filename}[{sid or i}]: messages/turns invalido")
            if filename=="multiturn_scenarios.json": multiturn.append(len(messages or []))
    schema=check("scenario_schemas_valid",not errors,f"{total} escenarios validos" if not errors else "; ".join(errors))
    multi=check("multiturn_coverage",bool(multiturn) and min(multiturn)>=2,f"{len(multiturn)} conversaciones; min/max {min(multiturn) if multiturn else 0}/{max(multiturn) if multiturn else 0}")
    return schema,multi

def isolation_check(root):
    errors=[]
    for path in (root/"app/agent_core_v2").glob("*.py"):
        try: tree=ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError: continue
        for node in ast.walk(tree):
            modules=[]
            if isinstance(node,ast.ImportFrom): modules=[node.module or ""]
            elif isinstance(node,ast.Import): modules=[x.name for x in node.names]
            if any(m.startswith("tools") for m in modules): errors.append(f"{path.name}:{node.lineno}")
    return check("runtime_isolated_from_lab_tools",not errors,"runtime aislado" if not errors else "imports tools: "+", ".join(errors))

def overfit_check(root):
    findings=[]
    for path in (root/"app/agent_core_v2").glob("*.py"):
        try: tree=ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError: continue
        for node in ast.walk(tree):
            if not isinstance(node,ast.Compare): continue
            candidates=[node.left,*node.comparators]; values=[]
            for c in candidates:
                if isinstance(c,ast.Constant) and isinstance(c.value,str): values.append(c.value)
                elif isinstance(c,(ast.Set,ast.Tuple,ast.List)): values += [x.value for x in c.elts if isinstance(x,ast.Constant) and isinstance(x.value,str)]
            if any(len(v.split())>=7 or len(v)>=80 for v in values): findings.append(f"{path.name}:{node.lineno}")
    return check("no_obvious_phrase_overfit",not findings,"sin comparaciones contra frases largas" if not findings else "revisar "+", ".join(findings))

def run(root):
    schema,multi=scenario_check(root)
    checks=[compile_check(root),runtime_check(root),schema,multi,isolation_check(root),overfit_check(root)]
    failed=[c.name for c in checks if c.blocking and not c.passed]
    return {"gate":"agent_core_v2_checkpoint","status":"failed" if failed else "passed","paid_llm_calls":0,"production_changed":False,"failed_checks":failed,"checks":[asdict(c) for c in checks]}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--root",default="."); p.add_argument("--output",default="artifacts/agent_core_v2_checkpoint.json"); a=p.parse_args()
    root=Path(a.root).resolve(); result=run(root); out=root/a.output; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result,ensure_ascii=False,indent=2)); print(f"Reporte: {out}"); return 0 if result["status"]=="passed" else 1
if __name__=="__main__": sys.exit(main())
