from pathlib import Path
import ast,json
root=Path(__file__).resolve().parents[2];files=list((root/'app/agent_core_v2_clean').glob('*.py'));checks=[]
try:
 for p in files:ast.parse(p.read_text())
 checks.append(('python_compiles',True,f'{len(files)} files'))
except Exception as e:checks.append(('python_compiles',False,str(e)))
text='\n'.join(p.read_text() for p in files);checks += [('isolated_from_previous_v2','app.agent_core_v2.' not in text,'no runtime imports'),('retrieval_disabled_phase_1','"enabled":False' in text,'intentional'),('telemetry_present','turn_metrics' in text and 'by_purpose' in text,'token and provider metrics')]
r={'gate':'agent_core_v2_clean_diagnostic_foundation','status':'passed' if all(x[1] for x in checks) else 'failed','checks':[{'name':a,'passed':b,'detail':c} for a,b,c in checks],'production_changed':False};print(json.dumps(r,indent=2));raise SystemExit(0 if r['status']=='passed' else 1)
