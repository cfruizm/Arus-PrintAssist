import sys,types
m=types.ModuleType('app.agent_core_v2_clean.models');m.AgentResponse=object;sys.modules['app.agent_core_v2_clean.models']=m
from app.agent_core_v2_clean.internal_knowledge import evidence_excerpt,validate_internal,SYSTEM

def test_relevant_evidence_is_selected_ahead_of_generic_content():
 r={'evidence':[{'id':'R1','title':'Overview','text':'General sustainability and product news.'},{'id':'R2','title':'Identity guide','text':'Synchronize user access codes from a corporate directory attribute and authenticate users.'}]}
 assert evidence_excerpt(r,'assign user access code','user authentication')[0]['id']=='R2'
def test_irrelevant_evidence_is_not_forced_into_excerpt():
 r={'evidence':[{'id':'R1','title':'Overview','text':'Sustainability pricing and release news.'}]};assert evidence_excerpt(r,'assign personal access code','user authentication')==[]
def test_complete_three_sections_pass():
 t='Lo que sí indica la documentación\nNo hay pasos.\nOrientación general complementaria\nRevise las alternativas.\nLímites y verificación necesaria\nConfirme la fuente oficial.';assert validate_internal(t,'stop',[])[0]
def test_length_is_rejected_before_retry():
 t='Lo que sí indica la documentación\nA\nOrientación general complementaria\nB\nLímites y verificación necesaria\nC';assert not validate_internal(t,'length',[])[0]
def test_prompt_requests_directory_paths_transversally():assert 'directorios corporativos' in SYSTEM and 'sincronización de atributos' in SYSTEM
def test_no_product_or_benchmark_rules():
 from pathlib import Path
 s=Path('app/agent_core_v2_clean/internal_knowledge.py').read_text().casefold()
 for x in ('papercut','active directory','ldap','template_fac','facturación'):assert x not in s
