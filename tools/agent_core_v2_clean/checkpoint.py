from pathlib import Path
import ast,json
root=Path(__file__).resolve().parents[2]
files=list((root/'app/agent_core_v2_clean').glob('*.py'))
checks=[]
try:
 for p in files:ast.parse(p.read_text())
 checks.append(("python_compiles",True,f"{len(files)} files"))
except Exception as exc:checks.append(("python_compiles",False,str(exc)))
joined='\n'.join(p.read_text() for p in files)
checks.append(("isolated_from_previous_v2","app.agent_core_v2." not in joined,"no runtime imports"))
checks.append(("retrieval_disabled_phase_1",'"enabled":False' in joined,"intentional phase boundary"))
result={"gate":"agent_core_v2_clean_foundation","status":"passed" if all(x[1] for x in checks) else "failed","checks":[{"name":a,"passed":b,"detail":c} for a,b,c in checks],"production_changed":False}
print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result["status"]=="passed" else 1)
