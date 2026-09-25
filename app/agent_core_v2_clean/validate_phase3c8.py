from src.exact_document_retrieval import document_identifiers,query_variants,exact_matches
from src.unified_evidence_authority import apply_unified_evidence_verdict
from src.topic_boundary import infer_topic_boundary

def item(i,title,text,source="/docs/AB0401-6_V1.pdf"):
 return {"id":f"R{i}","title":title,"source":source,"url":source,"page":str(i),"text":text,"metadata":{"source_name":source.rsplit("/",1)[-1]},"semantic_fit":{"score":.75}}
def run():
 ids=document_identifiers("AB0390-6 Analyze Dashboard Operations")
 rows=[item(1,"AB0435-6 V1 Technical Dashboard Manual","dashboard monitoring","/docs/AB0435-6_V1.pdf"),item(2,"AB0390-6 Analyze Dashboard Operations","operational analysis","/docs/AB0390-6.pdf")]
 hits=exact_matches(rows,ids);assert len(hits)==1 and "AB0390" in hits[0]["title"]
 ev=[item(1,"AB0401-6 V1 Instalar impresora por servidor","Procedimiento para instalar una impresora desde el servidor."),item(2,"AB0401-6 V1 Instalar impresora por servidor","Ejecutar, ingresar servidor, seleccionar impresora e instalar controlador.")]
 r={"query":{"fields":{"goal":"Explicar cómo instalar una impresora por servidor","current_message":"Como se instala una impresora por servidor?","details":{"subject":"Impresora por servidor"}}},"diagnostic_evidence":ev,"generation_evidence":ev,"semantic_fit":{"accepted_for_generation":True,"combined_quality":.8}}
 out=apply_unified_evidence_verdict(r,"Como se instala una impresora por servidor?",{"intent":"procedural","canonical_subject":"Impresora por servidor","current_goal":"Explicar cómo instalar una impresora por servidor","goal_updates":{"subject":"Impresora por servidor"}})
 assert out["evidence_verdict"]["accepted"]
 prev={"pending_goal":{"summary":"analizar dashboard","known_details":{"subject":"AB0435 manual dashboard"}},"active_subject":"AB0435 manual dashboard","support_case":{"status":"idle"}}
 u={"current_goal":"analizar dashboard","intent":"procedural","user_act":"follow_up","topic_relation":"same_topic","canonical_subject":"AB0390 dashboard operational","goal_updates":{"subject":"AB0390 dashboard operational"}}
 b=infer_topic_boundary(prev,u);assert b.relation=="same_topic_changed_scope" and b.previous_evidence_role=="comparison_only"
 v=query_variants("Revisar AB0421-6_V1 Operacion Herramienta","", "AB0421-6_V1 Operacion Herramienta");assert any("Operacion Herramienta" in x for x in v)
 policy=open(__file__.replace("validate_phase3c8.py","unified_evidence_authority.py")).read()+open(__file__.replace("validate_phase3c8.py","topic_boundary.py")).read()
 for forbidden in ("DA0390","DA0435","DA0401","DA0421","PaperCut","SIMP"):assert forbidden not in policy
 print({"passed":5,"failed":0,"phase":"3C.8"})
if __name__=="__main__":run()
