import ast,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R))
from app.agent_core_v2.evidence_budget import select_evidence
from app.agent_core_v2.answer_resilience import compose_resiliently

def item(i,app='direct',source=None,claim=None):
 return {'id':f'S{i}','title':f'Doc {i}','url':source or f'/doc{i}.pdf','text':'x'*3000,'query_relevance_score':10-i,'semantic_assessment':{'applicability':app,'subject_match':'same','task_match':'same','supported_claims':[claim or f'Claim {i}'],'conditions':[]}}
def main():
 ev={'citable':[item(i,source='/same.pdf' if i<5 else None) for i in range(1,44)]}
 s=select_evidence(ev,'conceptual');assert s['source_count']<=3 and s['total_chars']<=8000 and s['original_citable_count']==43
 ans,sel=compose_resiliently(intent='conceptual',evidence=ev,compose=lambda _:(_ for _ in ()).throw(RuntimeError('Límite de tokens de la sesión alcanzado.')))
 assert ans['mode']=='evidence_backed_recovery' and ans['fallback_reason']=='session_token_budget_exhausted' and ans['citations']
 ans2,_=compose_resiliently(intent='conceptual',evidence=ev,compose=lambda _:{'text':'respuesta válida','finish_reason':'stop'})
 assert ans2['text']=='respuesta válida'
 for path in (R/'app/agent_core_v2').glob('*.py'):ast.parse(path.read_text())
 print('PASS: budget, deduplication, failure taxonomy and evidence-backed recovery')
if __name__=='__main__':main()
