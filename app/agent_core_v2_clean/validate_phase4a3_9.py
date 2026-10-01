from src.source_footer import compact_sources,strip_generated_source_footer
from src.procedural_answer import _limit_web_document_chunks,_safe_cited_partial

def run():
 web=[{"id":"R1","title":"Web KB","url":"https://example.com/kb","page":""},{"id":"R2","title":"Web KB","url":"https://example.com/kb","page":""}]
 footer=compact_sources(web,["R1","R2"])
 assert footer=="**Fuente documental:** [Web KB](https://example.com/kb)"
 pdf=[{"id":"R1","title":"Guide","source":"/docs/a.pdf","page":"2"},{"id":"R2","title":"Guide","source":"/docs/a.pdf","page":"4"}]
 assert compact_sources(pdf,["R1","R2"])=="**Fuente documental:** Guide, págs. 2 y 4."
 body="Texto [R1]\n\n**Fuente documental:** vieja.\n\n**Fuentes documentales**\n- repetida"
 assert strip_generated_source_footer(body)=="Texto [R1]"
 many=[{"id":f"R{i}","title":"KB","url":"https://example.com/kb","text":"x"} for i in range(1,9)]
 assert len(_limit_web_document_chunks(many))==4
 partial,cited=_safe_cited_partial("**1. Uno**\nVerifica [R1]\n**2. Dos**\nTexto incompleto",["R1"],"length")
 assert partial.endswith("[R1]") and cited==["R1"]
 import pathlib
 root=pathlib.Path(__file__).parent;router=(root/"documented_router.py").read_text();lab=(root/"lab_session.py").read_text()
 assert "a.mode!='procedural_documented_answer_partial'" in router
 assert "phase4a3_9_source_provenance_budget_safe_publication" in lab
 print({"passed":7,"failed":0,"phase":"4A.3.9"})
if __name__=="__main__":run()
